export async function choosePageSize(scope,size){
  const page=typeof scope.page==='function'?scope.page():scope
  await scope.getByRole('combobox',{name:'每页条数',exact:true}).press('Enter')
  await page.getByRole('option',{name:`${size} 条/页`,exact:true}).click()
}
