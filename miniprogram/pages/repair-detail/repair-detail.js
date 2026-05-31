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
    picked: '',
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
      this.setData({ r, nextStatuses: NEXT[r.status] || [], picked: '' });
    } catch (e) {}
  },

  preview(e) {
    wx.previewImage({ urls: this.data.r.images, current: e.currentTarget.dataset.src });
  },
  onNote(e) { this.setData({ note: e.detail.value }); },
  pick(e) { this.setData({ picked: e.currentTarget.dataset.s }); },

  async doTransition() {
    try {
      await api.post(`/api/admin/repairs/${this.data.id}/transition`, {
        status: this.data.picked, note: this.data.note,
      });
      wx.showToast({ title: '已更新', icon: 'success' });
      this.setData({ note: '' });
      this.load();
    } catch (e) {}
  },
});
