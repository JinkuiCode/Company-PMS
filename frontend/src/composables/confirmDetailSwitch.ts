import { h } from 'vue'
import { ElButton, ElMessageBox } from 'element-plus'

export function confirmDetailSwitch(): Promise<'save' | 'discard' | 'cancel'> {
  return new Promise(resolve => {
    const choose = (decision: 'save' | 'discard' | 'cancel') => {
      resolve(decision)
      ElMessageBox.close()
    }
    void ElMessageBox({
      title: '未保存修改',
      message: h('div', [
        h('p', '当前记录有未保存的修改。'),
        h('div', { class: 'pms-detail-switch-actions' }, [
          h(ElButton, { onClick: () => choose('cancel') }, () => '取消'),
          h(ElButton, { onClick: () => choose('discard') }, () => '放弃修改并切换'),
          h(ElButton, { type: 'primary', onClick: () => choose('save') }, () => '保存后切换'),
        ]),
      ]),
      showConfirmButton: false,
      closeOnClickModal: false,
    }).then(() => resolve('cancel'), () => resolve('cancel'))
  })
}
