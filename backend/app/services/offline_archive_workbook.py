"""Read the confirmed archive template without Excel execution or formula evaluation."""
import io,zipfile,re,posixpath,hashlib
from datetime import datetime,timedelta
from xml.etree import ElementTree as ET
from fastapi import HTTPException
from app.models.dict import SysDict,SysDictItem
from app.services.offline_archive_fields import OFFLINE_FIELDS
NS={"s":"http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
REL="{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"
COLUMNS={"项目编号":"project_code","项目名称或内容":"project_name","来源分类":"archive_category","客户原称":"customer",
"客户名称原列":"customer_full_name","机型":"machine_model","设备系列":"equipment_series","设备序列号":"serial_no",
"数量":"quantity","单位":"quantity_unit","交货地点":"address_detail","编码日期":"legacy_code_date",
"更新日期":"legacy_updated_date","项目状态（原表）":"legacy_archive_status","交期说明":"delivery_note","备注":"remarks",
"联系人":"project_contact","联系电话":"contact_phone","销售公司":"sales_company"}
def _xml(z,path):
    data=z.read(path)
    if b"<!DOCTYPE" in data or b"<!ENTITY" in data:raise ValueError("XML entity declaration")
    return ET.fromstring(data)
def _sheet(z,name):
    workbook=_xml(z,"xl/workbook.xml")
    target=next((s for s in workbook.findall("s:sheets/s:sheet",NS) if s.get("name")==name),None)
    if target is None:return None
    rels=_xml(z,"xl/_rels/workbook.xml.rels")
    rel=next(r for r in rels if r.get("Id")==target.get(REL))
    if rel.get("TargetMode")=="External":raise ValueError("External relationship")
    path=posixpath.normpath("xl/"+rel.get("Target","")) if not rel.get("Target","").startswith("/") else rel.get("Target").lstrip("/")
    if not path.startswith("xl/"):raise ValueError("Invalid sheet path")
    return _xml(z,path)
def _records(z,name,shared):
    sheet=_sheet(z,name)
    if sheet is None:return []
    records=[]
    for row in sheet.findall("s:sheetData/s:row",NS):
        values={};next_index=0
        for c in row.findall("s:c",NS):
            ref=c.get("r","")
            if ref:
                letters=re.match("[A-Z]+",ref).group();index=0
                for x in letters:index=index*26+ord(x)-64
                index-=1
            else:index=next_index
            next_index=index+1
            if c.find("s:f",NS) is not None:raise ValueError("导入区域不能包含公式")
            typ=c.get("t")
            v=c.find("s:v",NS);value=v.text if v is not None else None
            if typ=="s":value=shared[int(value)]
            elif typ=="inlineStr":value="".join(c.itertext())
            elif typ=="e":value=None
            values[index]=value
        records.append(values)
    if not records:return []
    headers=records[0]
    return [{headers.get(i,""):v for i,v in row.items()} for row in records[1:]]
def read_archive_workbook(content):
    try:
        if len(content)>20*1024*1024:raise ValueError("文件超过20MB")
        with zipfile.ZipFile(io.BytesIO(content)) as z:
            if sum(i.file_size for i in z.infolist())>80*1024*1024:raise ValueError("解压内容超过80MB")
            shared=[]
            if "xl/sharedStrings.xml" in z.namelist():
                shared=["".join(si.itertext()) for si in _xml(z,"xl/sharedStrings.xml")]
            source=_records(z,"合并明细",shared)
            if not source or len(source)>10000:raise ValueError("找不到合并明细或超过10000条")
            raw={r.get("整理记录ID"):r for r in _records(z,"原始明细",shared)}
            output=[]
            for r in source:
                if not r.get("归档追溯ID") or not r.get("项目编号"):raise ValueError("缺少归档追溯ID或项目编号")
                position=r.get("来源位置") or ""
                match=re.search(r"!(\d+)$",position)
                if not match:raise ValueError("来源位置格式不正确")
                values={key:(r.get(label) or None) for label,key in COLUMNS.items()}
                for key in ("legacy_code_date","legacy_updated_date"):
                    v=values[key]
                    if v and re.fullmatch(r"\d+(\.\d+)?",v):
                        values[key]=(datetime(1899,12,30)+timedelta(days=float(v))).date().isoformat()
                if values.get("archive_category")=="售后（待分类）":values["archive_category"]="待分类"
                original=raw.get(r["归档追溯ID"],{})
                output.append({"source_id":r["归档追溯ID"],"source_sheet":r.get("来源工作表") or position.rsplit("!",1)[0],
                    "source_row":int(match.group(1)),"original_code":original.get("项目号") or original.get("编码") or values["project_code"],"values":values})
            return output
    except (ValueError,KeyError,TypeError,StopIteration,AttributeError,zipfile.BadZipFile,ET.ParseError,OverflowError) as exc:
        raise HTTPException(422,"无法读取档案修订表："+str(exc)) from exc
def prepare_workbook(db,content):
    from app.services.offline_archive_approval import APPROVED_FILE_HASH, approve_payload
    file_hash=hashlib.sha256(content).hexdigest()
    if file_hash != APPROVED_FILE_HASH:
        raise HTTPException(422,"仅支持已确认的第四版3024条档案，请选择原修订文件")
    rows=read_archive_workbook(content);errors=[];missing=set()
    enum_fields={k:v["enum_code"] for k,v in OFFLINE_FIELDS.items() if v["enum_code"]}
    enum_fields["equipment_series"]="equipment_series"
    maps={}
    for key,code in enum_fields.items():
        items=db.query(SysDictItem).join(SysDict,SysDict.id==SysDictItem.dict_id).filter(SysDict.dict_code==code,SysDict.status==1,SysDictItem.status==1).all()
        maps[key]={i.item_label:int(i.item_value) for i in items}
    for row in rows:
        for key,mapping in maps.items():
            value=row["values"].get(key)
            if value is None:continue
            if value not in mapping:
                missing.add((enum_fields[key],str(value)));row["values"][key]=None
            else:row["values"][key]=mapping[value]
    for code,label in sorted(missing):errors.append({"message":f"请先在枚举管理确认并新增选项：{code} / {label}","enum_code":code,"label":label})
    return {"payload":None if errors else approve_payload({"rows":rows},file_hash),"errors":errors,"file_hash":file_hash}
