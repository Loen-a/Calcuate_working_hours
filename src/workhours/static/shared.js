(() => {
  const form = document.querySelector('#legacy-import-form');
  if (!form) return;
  const status = document.querySelector('#backup-status');
  form.addEventListener('submit', async (event) => {
    event.preventDefault();
    if (!form.reportValidity()) return;
    if (!window.confirm('导入会覆盖备份包含的数据。建议先导出当前备份。确定继续？')) return;
    const payload = new FormData(form);
    const controls = [...document.querySelectorAll('button, input, select')];
    const previous = controls.map((control) => control.disabled);
    controls.forEach((control) => { control.disabled = true; });
    status.textContent = '正在校验并恢复备份…';
    try {
      const response = await fetch(form.action, { method: 'POST', body: payload });
      const result = await response.json();
      if (!response.ok) throw new Error(result.error || '导入失败');
      status.textContent = '备份已恢复，正在重新读取…';
      window.location.reload();
    } catch (error) {
      status.textContent = error instanceof Error ? error.message : '导入失败，请重试';
      controls.forEach((control, index) => { control.disabled = previous[index]; });
    }
  });
})();
