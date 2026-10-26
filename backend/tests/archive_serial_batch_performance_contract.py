"""Bounded batch SQL and semantics on disposable SQLite, never native MSSQL timing."""
import json
import os
from pathlib import Path
from time import perf_counter
from types import SimpleNamespace
import unittest

import sqlalchemy
from sqlalchemy import insert, text, update
from sqlalchemy.dialects import mssql
from sqlalchemy.orm import Session
from fastapi import HTTPException
from pydantic import ValidationError
import archive_serial_namespace_contract as fixtures
import archive_serial_mssql_contract as native
from app.models.archive_change import ArchiveChange
from app.models.form_draft import PmsFormDraft
from app.models.project import PmsProjectArchive
from app.schemas.offline_archive import ImportPayload
from app.services.archive_code_unique import lock_codes, require_identity_lock
from app.services.archive_serial_unique import identity_batch_conflicts

MEASUREMENTS = []


class Result:
    def __init__(self, result, record):
        self.result, self.record = result, record

    def read(self, consume):
        started = perf_counter()
        try:
            return consume()
        finally:
            self.record['fetch_seconds'] += perf_counter() - started

    def scalar(self):
        return self.read(self.result.scalar)

    def scalars(self):
        return self.read(lambda: list(self.result.scalars()))

    def __iter__(self):
        return iter(self.read(self.result.all))


class QueryProbe:
    def __init__(self, connection, fake_mssql=False):
        self.connection, self.info = connection, connection.info
        self.dialect = SimpleNamespace(name='mssql') if fake_mssql else connection.dialect
        self.fake_mssql, self.records = fake_mssql, []

    def get_transaction(self):
        return self.connection.get_transaction()

    def execute(self, statement, parameters=None):
        started = perf_counter()
        compiled = statement.compile(dialect=mssql.dialect(), compile_kwargs={'render_postcompile': True})
        mssql_seconds = perf_counter() - started
        started = perf_counter()
        sqlite = statement.compile(dialect=self.connection.dialect, compile_kwargs={'render_postcompile': True})
        record = {'pair': list(getattr(statement, 'selected_columns', {}).keys()) == ['slot', 'slot_1'],
                  'formal': list(getattr(statement, 'selected_columns', {}).keys()) == ['slot'] and 'JOIN pms_project_archive ON' in str(compiled),
                  'mssql_sql': str(compiled), 'sqlite_sql': str(sqlite), 'parameters': compiled.params,
                  'parameter_types': {name: str(compiled.binds[name].type) for name in compiled.params},
                  'mssql_compile_seconds': mssql_seconds, 'sqlite_compile_seconds': perf_counter() - started,
                  'execute_seconds': 0.0, 'fetch_seconds': 0.0}
        self.records.append(record)
        if self.fake_mssql and 'collation_name' in str(statement):
            return Result(native.Scalar('SERIAL_TEST'), record)
        started = perf_counter()
        try:
            result = native.execute_on_sqlite(self.connection, statement, parameters) if self.fake_mssql else self.connection.execute(statement, parameters or {})
        finally:
            record['execute_seconds'] = perf_counter() - started
        return Result(result, record)


class BatchPerformance(unittest.TestCase):
    def setUp(self):
        self.fixture = fixtures.Namespace()
        self.fixture.setUp()
        with self.fixture.engine.connect() as connection:
            connection.connection.driver_connection.create_collation(
                'SERIAL_TEST', lambda a, b: (a.replace('_', '') > b.replace('_', '')) -
                (a.replace('_', '') < b.replace('_', '')))
            ddl = connection.scalar(text("SELECT sql FROM sqlite_master WHERE name='pms_project_archive'"))
            connection.exec_driver_sql('DROP TABLE pms_project_archive')
            connection.exec_driver_sql(ddl.replace('serial_no_key NVARCHAR(64)',
                                                 'serial_no_key NVARCHAR(64) COLLATE SERIAL_TEST'))
            connection.commit()

    def tearDown(self):
        self.fixture.tearDown()

    def measured(self, connection, proposals, label, fake_mssql=False):
        started = perf_counter()
        expected = identity_batch_conflicts(connection, proposals)
        function_seconds = perf_counter() - started
        probe = QueryProbe(connection, fake_mssql)
        started = perf_counter()
        actual = identity_batch_conflicts(probe, proposals)
        instrumented_seconds = perf_counter() - started
        self.assertEqual(actual, expected)
        compile_seconds = sum(r['mssql_compile_seconds'] + r['sqlite_compile_seconds'] for r in probe.records)
        execute_seconds = sum(r['execute_seconds'] for r in probe.records)
        fetch_seconds = sum(r['fetch_seconds'] for r in probe.records)
        MEASUREMENTS.append({'case': label, 'function_sqlite_wall_seconds': function_seconds,
                             'instrumented_wall_seconds': instrumented_seconds,
                             'construction_and_python_residual_seconds': instrumented_seconds - compile_seconds - execute_seconds - fetch_seconds,
                             'note': 'residual includes Python validation/probe overhead; execute/fetch are client SQLite, not SQL Server server time',
                             'statements': probe.records})
        require_identity_lock(connection)
        return actual, probe.records

    def test_same_chunk_candidate_sql_defines_each_pair_input_once(self):
        with self.fixture.engine.connect() as connection:
            lock_codes(connection)
            proposals = [{'serial_no': 'same' if i in (0, 149) else f'only-{i}'} for i in range(150)]
            conflicts, records = self.measured(connection, proposals, 'same-chunk-150', fake_mssql=True)
            self.assertEqual(conflicts, [(0, 'serial_no'), (149, 'serial_no')])
            pairs = [r for r in records if r['pair']]
            self.assertEqual(len(pairs), 1)
            self.assertEqual(len(pairs[0]['parameters']), 300, 'one slot/key binding per candidate, no repeated same-chunk input')
            self.assertEqual(pairs[0]['mssql_sql'].upper().count('UNION ALL'), 149)
            self.assertTrue(pairs[0]['mssql_sql'].startswith('WITH '))

    def test_candidate_and_occupied_boundaries_preserve_original_slots_and_native_equivalence(self):
        cases = [(n, 0) for n in (150, 151, 300, 301, 400, 401, 1000)]
        cases += [(151, 300), (301, 301), (400, 400), (401, 401), (1000, 401)]
        for size, occupied in cases:
            with self.subTest(size=size, occupied=occupied), self.fixture.engine.connect() as connection:
                lock_codes(connection)
                proposals = [{}] + [{'serial_no': f'unique-{i}'} for i in range(size)] + [{'serial_no': None}]
                proposals[1]['serial_no'], proposals[size]['serial_no'] = 'A_B', 'ab'
                proposals[2]['serial_no'], proposals[3]['serial_no'] = 'X_Y', 'xy'
                expected = {(slot, 'serial_no') for slot in (1, 2, 3, size)}
                for i in range(occupied):
                    self.fixture.occupy(connection, 'draft', f'occupied-{i}', f'private-{i}')
                if occupied:
                    proposals[4]['serial_no'] = f'occupied-{occupied-1}'
                    expected.add((4, 'serial_no'))
                conflicts, records = self.measured(connection, proposals, f'batch-{size}-occupied-{occupied}')
                self.assertEqual(conflicts, sorted(expected))
                chunks = (size + 149) // 150
                self.assertEqual(sum(r['pair'] for r in records), chunks * (chunks + 1) // 2)
                self.assertTrue(all(len(r['parameters']) <= 750 for r in records))
                connection.rollback()

    def test_only_each_proposals_own_formal_is_excluded_not_drafts_or_pending(self):
        with self.fixture.engine.connect() as connection:
            lock_codes(connection)
            first = self.fixture.formal(connection, 'SELF-A', 'first')
            second = self.fixture.formal(connection, 'SELF-B', 'second')
            connection.execute(update(PmsProjectArchive).where(PmsProjectArchive.id == second).values(is_enabled=0))
            self.assertEqual(identity_batch_conflicts(connection, [{'serial_no': 'first', 'archive_id': first}, {'serial_no': 'second', 'archive_id': second}]), [])
            self.assertEqual(identity_batch_conflicts(connection, [{'serial_no': 'first', 'archive_id': second}, {'serial_no': 'second', 'archive_id': first}]), [(0, 'serial_no'), (1, 'serial_no')])
            self.assertEqual(identity_batch_conflicts(connection, [{'serial_no': 'second'}]), [(0, 'serial_no')])
            self.fixture.occupy(connection, 'draft', 'first', 'PRIVATE-CODE')
            self.fixture.occupy(connection, 'pending', 'second', 'pending')
            self.assertEqual(identity_batch_conflicts(connection, [{'serial_no': 'first', 'archive_id': first}, {'serial_no': 'second', 'archive_id': second}, {'project_code': 'private-code'}]), [(0, 'serial_no'), (1, 'serial_no'), (2, 'project_code')])

    def test_damaged_occupancy_fails_closed_even_when_no_candidates(self):
        for payload in ('[]', '{', '{"serial_no":0}', '{"project_code":false}'):
            with self.subTest(payload=payload), self.fixture.engine.connect() as connection:
                lock_codes(connection)
                connection.execute(insert(PmsFormDraft).values(id='invalid', owner_id=1, resource='archive-create', status='active', payload_json=payload))
                with self.assertRaises(HTTPException) as error:
                    identity_batch_conflicts(connection, [])
                self.assertEqual(error.exception.detail['code'], 'ARCHIVE_SERIAL_UNAVAILABLE')
                connection.rollback()
        with self.fixture.engine.connect() as connection:
            lock_codes(connection)
            self.fixture.occupy(connection, 'pending', 'held', 'pending')
            for changes in ({'status': 3}, {'active_archive_id': None}, {'archive_id': 999999, 'active_archive_id': 999999}, {'updates_json': '[]'}):
                nested = connection.begin_nested()
                connection.execute(update(ArchiveChange).values(**changes))
                with self.assertRaises(HTTPException):
                    identity_batch_conflicts(connection, [{'serial_no': 'held'}, {'serial_no': 'held'}])
                nested.rollback()

    def test_missing_or_ended_outer_transaction_fails_closed(self):
        with self.fixture.engine.connect() as connection:
            with self.assertRaises(HTTPException):
                identity_batch_conflicts(connection, [])
            lock_codes(connection)
            transaction = connection.get_transaction()
            identity_batch_conflicts(connection, [{'serial_no': 'safe'}])
            self.assertIs(connection.get_transaction(), transaction)
            connection.commit()
            with self.assertRaises(HTTPException):
                identity_batch_conflicts(connection, [{'serial_no': 'safe'}])

    def test_zero_and_false_are_rejected_at_existing_import_schema_boundary(self):
        for field in ('project_code', 'serial_no'):
            for value in (0, False):
                with self.subTest(field=field, value=value), self.assertRaises(ValidationError):
                    ImportPayload.model_validate({'rows': [{'source_id': 'synthetic', 'source_sheet': 'fixture', 'source_row': 2, 'values': {'project_code': 'VALID', field: value}}]})

    def test_import_plan_preserves_matched_formal_and_maps_native_conflicts_to_sources(self):
        from app.services.offline_archive_reconciliation import build_import_plan
        from app.services.offline_archive_import import digest
        from app.services.operation_log import serialize_model
        with self.fixture.engine.connect() as connection:
            lock_codes(connection)
            archive_id = self.fixture.formal(connection, 'EXISTING', 'owned')
            with Session(bind=connection) as db:
                payload = ImportPayload.model_validate({'reconcile_existing': True, 'rows': [
                    {'source_id': source, 'source_sheet': 'fixture', 'source_row': index + 2,
                     'values': {'project_code': code, 'serial_no': serial}}
                    for index, (source, code, serial) in enumerate([
                        ('matched', 'EXISTING', 'do-not-overwrite'),
                        ('left', 'NEW-LEFT', 'A_B'), ('right', 'NEW-RIGHT', 'ab')])]}).model_dump(mode='json')
                payload['targets'] = {'matched': {'archive_id': archive_id,
                    'snapshot_hash': digest(serialize_model(db.get(PmsProjectArchive, archive_id)))}}
                plan, errors = build_import_plan(db, payload)
                self.assertNotIn('serial_no', plan[0][2])
                self.assertEqual({(error['source_id'], error['field']) for error in errors},
                                 {('left', 'serial_no'), ('right', 'serial_no')})
                self.assertEqual(db.get(PmsProjectArchive, archive_id).serial_no, 'owned')
                require_identity_lock(connection)

    def test_mssql_formal_rowsets_are_compact_typed_and_preserve_sqlite_results(self):
        for size in (1, 150, 151, 300, 301, 400, 401, 1000):
            with self.subTest(size=size), self.fixture.engine.connect() as connection:
                lock_codes(connection)
                own = self.fixture.formal(connection, 'OWN', 'A_B')
                other = self.fixture.formal(connection, 'OTHER', 'C_D')
                self.fixture.formal(connection, 'THIRD', 'E_F')
                connection.execute(update(PmsProjectArchive).where(PmsProjectArchive.id == other).values(is_enabled=0))
                proposals = [{}] + [
                    {'project_code': f'P-{i}', 'serial_no': f'SN-{i}',
                     'archive_id': own if i % 2 else None} for i in range(size)] + [{}]
                proposals[1] = {'project_code': 'OWN', 'serial_no': 'ab', 'archive_id': own}
                expected = []
                if size > 1:
                    proposals[2] = {'project_code': 'OTHER', 'serial_no': 'cd', 'archive_id': own}
                    expected += [(2, 'project_code'), (2, 'serial_no')]
                if size > 2:
                    proposals[size] = {'project_code': 'THIRD', 'serial_no': 'ef', 'archive_id': None}
                    expected += [(size, 'project_code'), (size, 'serial_no')]
                if size > 3:
                    proposals[3] = {'project_code': "测'--", 'serial_no': "Ω_Ａ'--", 'archive_id': None}
                conflicts, records = self.measured(connection, proposals, f'formal-{size}', fake_mssql=True)
                self.assertEqual(conflicts, sorted(expected))
                formal = [r for r in records if r['formal']]
                self.assertEqual(len(formal), 2 * ((size + 149) // 150))
                chunks = (size + 149) // 150
                for index, record in enumerate(formal):
                    self.assertIn('FROM (VALUES ', record['mssql_sql'])
                    start = 1 + (index % chunks) * 150
                    chunk = proposals[start:min(start + 150, size + 1)]
                    expected_types = [kind for row in chunk for kind in
                                      (['INTEGER', 'NVARCHAR(64)'] + (['INTEGER'] if row['archive_id'] is not None else []))]
                    self.assertEqual(len(record['parameters']), len(expected_types))
                    self.assertNotIn(None, record['parameters'].values())
                    if any(row['archive_id'] is None for row in chunk):
                        self.assertIn('CAST(NULL AS INTEGER)', record['mssql_sql'])
                    self.assertNotIn("测'--", record['mssql_sql'])
                    self.assertNotIn("ω_ａ'--", record['mssql_sql'])
                    self.assertNotIn('UNION ALL', record['mssql_sql'])
                    self.assertLessEqual(len(record['parameters']), 450)
                    self.assertIn('archive_id IS NULL OR pms_project_archive.id !=', record['mssql_sql'])
                    types = list(record['parameter_types'].values())
                    self.assertEqual(types, expected_types)
                connection.rollback()

    def test_mssql_candidates_do_not_bind_missing_archive_ids(self):
        for occupied in (0, 301):
            with self.subTest(occupied=occupied), self.fixture.engine.connect() as connection:
                lock_codes(connection)
                proposals = [{}] + [{'project_code': f'P-{i}', 'serial_no': f'SN-{i}'}
                                    for i in range(151)] + [{}]
                proposals[1]['serial_no'], proposals[151]['serial_no'] = 'A_B', 'ab'
                expected = [(1, 'serial_no'), (151, 'serial_no')]
                for i in range(occupied):
                    self.fixture.occupy(connection, 'draft', f'held-{i}', f'private-{i}')
                if occupied:
                    proposals[2]['serial_no'] = 'held-300'
                    expected.append((2, 'serial_no'))
                conflicts, records = self.measured(connection, proposals, f'null-free-151-{occupied}', fake_mssql=True)
                self.assertEqual(conflicts, sorted(expected))
                candidates = [r for r in records if r['formal'] or r['pair'] or ' AS archive_id' in r['mssql_sql']]
                self.assertTrue(candidates)
                for record in candidates:
                    self.assertNotIn(None, record['parameters'].values(), 'missing archive IDs must remain typed SQL NULL, not driver-bound None')
                self.assertEqual([len(r['parameters']) for r in records if r['formal']], [300, 2, 300, 2])
                self.assertEqual([len(r['parameters']) for r in records if r['pair']], [300, 302, 2])
                self.assertTrue(any('CAST(NULL AS INTEGER)' in r['mssql_sql'] for r in candidates))
                connection.rollback()


if __name__ == '__main__':
    assert sqlalchemy.__version__ == '2.0.37'
    try:
        unittest.main(verbosity=2)
    finally:
        output = os.environ.get('PMS_SERIAL_PERF_OUTPUT')
        if output:
            Path(output).write_text(json.dumps({'sqlalchemy': sqlalchemy.__version__, 'native_mssql_executed': False, 'measurements': MEASUREMENTS}, indent=2) + '\n')