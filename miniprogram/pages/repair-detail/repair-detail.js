const api = require('../../utils/api');

const STATUS_TEXT = {
  submitted: '待受理', assigned: '已分配', in_progress: '维修中', done: '已完成', closed: '已关闭',
};
const STATUS_CLASS = {
  submitted: 'tag-orange', assigned: 'tag-blue', in_progress: 'tag-blue', done: 'tag-green', closed: 'tag-gray',
};
// 与后端 repair_service.TRANSITIONS 保持一致
const NEXT = {
  submitted: ['assigned', 'closed'],
  assigned: ['in_progress', 'closed'],
  in_progress: ['done', 'closed'],
  done: ['closed', 'in_progress'],
  closed: [],
};

Page({
  data: {
    id: null,
    r: { logs: [], images: [] },
    isAdmin: false,
    nextStatuses: [],
    note: '',
    statusText: STATUS_TEXT,
    statusClass: STATUS_CLASS,
  },

  onLoad(q) {
    this.setData({
      id: Number(q.id),
      isAdmin: getApp().globalData.userInfo && getApp().globalData.userInfo.role === 'admin',
    });
    this.load();
  },

  async load() {
    try {
      const r = await api.get('/api/repairs/' + this.data.id);
      this.setData({ r, nextStatuses: NEXT[r.status] || [] });
    } catch (e) {}
  },

  preview(e) {
    wx.previewImage({ urls: this.data.r.images, current: e.currentTarget.dataset.src });
  },
  onNote(e) { this.setData({ note: e.detail.value }); },

  // 点击状态 -> 弹确认 -> 直接更新（一步到位）
  async confirmTransition(e) {
    const status = e.currentTarget.dataset.s;
    const label = STATUS_TEXT[status] || status;
    const ok = await new Promise((resolve) => wx.showModal({
      title: '流转工单',
      content: `确认将工单状态更新为「${label}」？`,
      success: (m) => resolve(m.confirm),
    }));
    if (!ok) return;
    try {
      await api.post(`/api/admin/repairs/${this.data.id}/transition`, {
        status, note: this.data.note,
      });
      wx.showToast({ title: '已更新为' + label, icon: 'success' });
      this.setData({ note: '' });
      this.load();
    } catch (e) {}
  },
});
