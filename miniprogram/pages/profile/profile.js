const api = require('../../utils/api');

Page({
  data: {
    user: {},
    bookings: [],
    roleText: { student: '学生', teacher: '教师', admin: '管理员' },
    bkText: { pending: '待审批', approved: '已通过', rejected: '已驳回', cancelled: '已取消' },
    bkClass: { pending: 'tag-orange', approved: 'tag-green', rejected: 'tag-gray', cancelled: 'tag-gray' },
  },

  onShow() {
    const app = getApp();
    if (!app.globalData.token) { wx.reLaunch({ url: '/pages/login/login' }); return; }
    this.setData({ user: app.globalData.userInfo || {} });
    this.loadBookings();
  },

  async loadBookings() {
    try {
      const bookings = await api.get('/api/bookings/mine');
      this.setData({ bookings });
    } catch (e) {}
  },

  async cancel(e) {
    const id = e.currentTarget.dataset.id;
    const ok = await new Promise((r) => wx.showModal({ title: '确认取消该预约？', success: (m) => r(m.confirm) }));
    if (!ok) return;
    try {
      await api.post(`/api/bookings/${id}/cancel`);
      wx.showToast({ title: '已取消', icon: 'success' });
      this.loadBookings();
    } catch (e) {}
  },

  goAdmin() { wx.navigateTo({ url: '/pages/admin/admin' }); },
  logout() { getApp().logout(); },
});
