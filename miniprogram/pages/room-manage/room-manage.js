const api = require('../../utils/api');

const EMPTY = { name: '', location: '', capacity: '', open_time: '08:00', close_time: '22:00', description: '' };

Page({
  data: {
    rooms: [],
    total: 0,
    showForm: false,
    editId: null,
    form: { ...EMPTY },
  },

  onShow() {
    const u = getApp().globalData.userInfo;
    if (!u || u.role !== 'admin') { wx.navigateBack(); return; }
    this.load();
  },

  async load() {
    try {
      const rooms = await api.get('/api/admin/rooms');
      this.setData({ rooms, total: rooms.length });
    } catch (e) {}
  },

  // ---------- 新增 / 编辑 ----------
  openCreate() { this.setData({ showForm: true, editId: null, form: { ...EMPTY } }); },
  openEdit(e) {
    const r = e.currentTarget.dataset.room;
    this.setData({
      showForm: true, editId: r.id,
      form: {
        name: r.name, location: r.location || '', capacity: String(r.capacity || ''),
        open_time: r.open_time, close_time: r.close_time, description: r.description || '',
      },
    });
  },
  closeForm() { this.setData({ showForm: false }); },
  onField(e) { this.setData({ ['form.' + e.currentTarget.dataset.k]: e.detail.value }); },

  async saveForm() {
    const f = this.data.form;
    if (!f.name.trim()) { wx.showToast({ title: '请填写名称', icon: 'none' }); return; }
    const body = {
      name: f.name.trim(), location: f.location, capacity: Number(f.capacity) || 0,
      open_time: f.open_time, close_time: f.close_time, description: f.description,
    };
    try {
      if (this.data.editId) await api.put('/api/admin/rooms/' + this.data.editId, body);
      else await api.post('/api/admin/rooms', body);
      wx.showToast({ title: '已保存', icon: 'success' });
      this.setData({ showForm: false });
      this.load();
    } catch (e) {}
  },

  // ---------- 启用 / 停用 ----------
  _confirm(title, content) {
    return new Promise((r) => wx.showModal({ title, content, success: (m) => r(m.confirm) }));
  },

  async enable(e) {
    try {
      await api.patch(`/api/admin/rooms/${e.currentTarget.dataset.id}/active?active=true`);
      wx.showToast({ title: '已启用', icon: 'success' });
      this.load();
    } catch (e) {}
  },

  async disable(e) {
    const id = e.currentTarget.dataset.id;
    let impact;
    try { impact = await api.get(`/api/admin/rooms/${id}/impact`); } catch (e) { return; }
    const summary = `未来预约 ${impact.future_bookings} 条（师生 ${impact.user_bookings}、课表 ${impact.course_bookings}），未完成报修 ${impact.open_repairs} 个。课表占用将被清除（需重新导入）。`;

    if (impact.user_bookings === 0) {
      if (!(await this._confirm('停用场地', summary + '\n确定停用？'))) return;
      this._doDisable(id, { action: 'cancel' });
      return;
    }
    // 有师生预约：选择处理方式
    const choice = await new Promise((r) => wx.showActionSheet({
      itemList: ['取消全部预约并停用', '迁移到其他场地后停用'],
      success: (s) => r(s.tapIndex), fail: () => r(-1),
    }));
    if (choice === 0) {
      if (!(await this._confirm('确认取消', `将取消 ${impact.user_bookings} 条师生预约并通知用户。\n` + summary))) return;
      this._doDisable(id, { action: 'cancel' });
    } else if (choice === 1) {
      const targets = this.data.rooms.filter((r) => r.id !== id && r.is_active);
      if (!targets.length) { wx.showToast({ title: '没有其他可用场地', icon: 'none' }); return; }
      const idx = await new Promise((r) => wx.showActionSheet({
        itemList: targets.map((t) => t.name),
        success: (s) => r(s.tapIndex), fail: () => r(-1),
      }));
      if (idx < 0) return;
      this._doDisable(id, { action: 'relocate', target_room_id: targets[idx].id });
    }
  },

  async _doDisable(id, body) {
    try {
      const res = await api.patch(`/api/admin/rooms/${id}/active?active=false`, body);
      let msg = `已停用。迁移 ${res.relocated || 0} 条 · 取消 ${res.cancelled || 0} 条 · 清除课表 ${res.course_cancelled || 0} 条。`;
      if (res.conflicts && res.conflicts.length) {
        msg += `\n有 ${res.conflicts.length} 条因目标场地时段冲突未迁移，仍在原场地，请稍后单独改约或取消。`;
      }
      wx.showModal({ title: '停用完成', content: msg, showCancel: false });
      this.load();
    } catch (e) {}
  },

  async remove(e) {
    const id = e.currentTarget.dataset.id;
    let impact;
    try { impact = await api.get(`/api/admin/rooms/${id}/impact`); } catch (e) { return; }

    if (impact.future_bookings > 0) {
      wx.showModal({
        title: '无法删除',
        content: '该场地仍有未来有效预约，请先「停用」并处理（取消或迁移）后再删除。',
        showCancel: false,
      });
      return;
    }
    const totalRecords = (impact.total_bookings || 0) + (impact.total_repairs || 0);
    let force = false;
    let content = '该场地无任何记录，确定物理删除？';
    if (totalRecords > 0) {
      force = true;
      content = `该场地有 ${impact.total_bookings} 条预约、${impact.total_repairs} 条报修历史记录（含已取消/已完成）。物理删除会一并清除并影响历史报表，建议改用「停用」。仍要强制删除？`;
    }
    if (!(await this._confirm(force ? '强制删除' : '物理删除', content))) return;
    try {
      await api.del(`/api/admin/rooms/${id}${force ? '?force=true' : ''}`);
      wx.showToast({ title: '已删除', icon: 'success' });
      this.load();
    } catch (e) {}
  },
});
