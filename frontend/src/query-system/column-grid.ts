import PmsQueryColumnHeader from './PmsQueryColumnHeader.vue'
import type { ColDef, ColGroupDef } from 'ag-grid-community'
import type { ColumnQueryContext } from './column-filters'
export function decorateQueryColumns<T>(definitions:(ColDef<T>|ColGroupDef<T>)[],context:()=>ColumnQueryContext):(ColDef<T>|ColGroupDef<T>)[] {
  context().filters()
  return definitions.map(def=>{
    if('children' in def)return {...def,children:decorateQueryColumns(def.children,context)}
    const field=String(def.field||'')
    if(!field||!context().fields().some(f=>f.field===field))return def
    const previous=def.cellClass,header=def.headerClass
    return {...def,headerComponent:PmsQueryColumnHeader,headerComponentParams:{contextQuery:context,field},
      cellClass:previous,
      cellClassRules:{...def.cellClassRules,'pms-query-filtered-column':()=>context().filters().some(f=>f.field===field)},
      headerClass:(params:any)=>[...(typeof header==='function'?[header(params)]:Array.isArray(header)?header:header?[header]:[]),...(context().filters().some(f=>f.field===field)?['pms-query-filtered-column']:[])].flat().filter((v):v is string=>typeof v==='string'),
    }
  })
}
