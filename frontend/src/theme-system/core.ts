export const THEMES = {
  blue: { name:'办公蓝', brand:'#2563eb', hover:'#1d4ed8', soft:'#eff6ff', accentBorder:'#bfdbfe', bg:'#f5f7fa', text:'#20242b', secondary:'#5f6b7a', muted:'#6f7b8b', border:'#dce1e7', line:'#eaf0f5', head:'#f5f7fa', rowHover:'#f5f8fc', selected:'#edf4ff' },
  teal: { name:'青绿', brand:'#0f766e', hover:'#115e59', soft:'#eaf5f1', accentBorder:'#b5dcd0', bg:'#f5f8f7', text:'#202824', secondary:'#586c64', muted:'#6b7c75', border:'#dce4e0', line:'#eaf0ec', head:'#f3f7f5', rowHover:'#f2f8f5', selected:'#eaf5f1' },
  graphite: { name:'石墨', brand:'#27272a', hover:'#09090b', soft:'#f0f0f3', accentBorder:'#ccccd4', bg:'#f7f7f8', text:'#202023', secondary:'#62626c', muted:'#72727c', border:'#e1e1e5', line:'#eeeef1', head:'#f5f5f6', rowHover:'#f6f6f8', selected:'#efeff3' },
} as const
export type ThemeId = keyof typeof THEMES
export const normalizeTheme = (value:unknown):ThemeId => typeof value==='string'&&Object.hasOwn(THEMES,value)?value as ThemeId:'blue'
export type ThemeStorage = Pick<Storage,'getItem'|'setItem'>
type ThemeRoot = Pick<HTMLElement,'getAttribute'|'setAttribute'|'removeAttribute'> & {style:Pick<CSSStyleDeclaration,'getPropertyValue'|'getPropertyPriority'|'setProperty'|'removeProperty'>}
type Options = {environment:string;root:ThemeRoot;storage?:ThemeStorage;events?:Pick<EventTarget,'addEventListener'|'removeEventListener'>;publicUser?:string}
const attribute='data-pms-theme'

export function themeTokens(id:ThemeId):Record<string,string>{
  const t=THEMES[id]
  return {
    '--pms-primary':t.brand,'--pms-primary-hover':t.hover,'--pms-primary-soft':t.soft,
    '--pms-accent-border':t.accentBorder,'--pms-bg':t.bg,'--pms-bg-soft':t.head,
    '--pms-text':t.text,'--pms-text-secondary':t.secondary,'--pms-text-muted':t.muted,
    '--pms-border':t.border,'--pms-border-soft':t.line,'--pms-frozen-divider':t.border,
    '--pms-surface':'#ffffff','--pms-surface-muted':t.head,'--pms-row-hover':t.rowHover,'--pms-row-selected':t.selected,
    '--pms-success':'#087e65','--pms-success-soft':'#edf8f3','--pms-warning':'#9a6400','--pms-warning-soft':'#fff6e7',
    '--pms-danger':'#c83434','--pms-danger-soft':'#fff0ef','--pms-info':t.brand,'--pms-info-soft':t.soft,
    '--pms-neutral-soft':t.head,'--pms-progress-low':'#c83434','--pms-progress-mid':'#b68b00','--pms-progress-complete':'#087e65',
    '--pms-radius-sm':'4px','--pms-radius':'6px','--pms-radius-lg':'8px',
    '--pms-shadow-sm':'0 2px 5px #20242b08,0 8px 24px #20242b12',
  }
}

export function createThemeSession(options:Options){
  const {root,storage,events}=options
  const previousAttribute=root.getAttribute(attribute)
  const previousStyles=Object.keys(themeTokens('blue')).map(key=>({key,value:root.style.getPropertyValue(key),priority:root.style.getPropertyPriority(key)}))
  const listeners=new Set<()=>void>()
  let user:string|null=null,theme:ThemeId='blue',disposed=false
  const publicKey=`pms:theme:public:v1:${encodeURIComponent(options.environment)}`
  const key=()=>user===null?'':user===options.publicUser?publicKey:`pms:theme:v1:${encodeURIComponent(options.environment)}:${encodeURIComponent(user)}`
  const notify=()=>listeners.forEach(listener=>listener())
  function restore(){
    if(previousAttribute===null)root.removeAttribute(attribute);else root.setAttribute(attribute,previousAttribute)
    for(const item of previousStyles){if(item.value)root.style.setProperty(item.key,item.value,item.priority);else root.style.removeProperty(item.key)}
  }
  function apply(next:ThemeId){
    theme=next;root.setAttribute(attribute,theme)
    for(const [name,value] of Object.entries(themeTokens(theme)))root.style.setProperty(name,value)
  }
  function read():ThemeId{try{return normalizeTheme(storage?.getItem(key()))}catch{return 'blue'}}
  function setUser(id:string|number|null|undefined){
    if(disposed)return
    const next=id===null||id===undefined||id===''?null:String(id)
    if(next===user)return
    user=next
    if(user===null){theme='blue';restore()}else{
      apply(read())
      if(options.publicUser&&user!==options.publicUser){try{storage?.setItem(publicKey,theme)}catch{/* Appearance hint is optional. */}}
    }
    notify()
  }
  function choose(value:unknown){
    if(disposed||user===null)return {applied:false,persisted:false}
    apply(normalizeTheme(value));let persisted=false
    try{if(storage){storage.setItem(key(),theme);persisted=true}}catch{/* Session selection remains usable. */}
    if(options.publicUser&&user!==options.publicUser){try{storage?.setItem(publicKey,theme)}catch{/* Never include an identity in the public hint. */}}
    notify();return {applied:true,persisted}
  }
  function storageChanged(event:Event){
    const change=event as StorageEvent
    if(disposed||user===null||(change.key!==null&&change.key!==key())||(change.storageArea&&change.storageArea!==storage))return
    apply(read());notify()
  }
  events?.addEventListener('storage',storageChanged)
  return {
    get theme(){return theme},get active(){return user!==null&&!disposed},get key(){return key()},
    setUser,choose,
    subscribe(listener:()=>void){listeners.add(listener);return()=>{listeners.delete(listener)}},
    dispose(){if(disposed)return;disposed=true;user=null;theme='blue';events?.removeEventListener('storage',storageChanged);restore();notify();listeners.clear()},
  }
}
export type ThemeSession = ReturnType<typeof createThemeSession>
