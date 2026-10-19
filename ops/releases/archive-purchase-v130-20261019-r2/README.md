# v1.3.0 R2 rehearsal preparation

R1 backup verification and new isolated restore passed. Conversion correctly rejected the synthetic fixture because customer was missing under the existing production field policy. Read-only diagnosis reproduced this exact 422, with the draft still active at version 3. Application candidate 5c5baea remains unchanged.

R2 only fills the synthetic customer field. A new integration regression reads the exact probe fixture and runs real draft conversion/replay with customer required; a negative case still rejects missing customer and keeps the draft. R0/R1 directories, backups and isolated databases remain preserved. R2 uses a fresh directory and random isolated database, with approval unset pending permission to retry. Formal deployment remains unapproved.
