const api = require('../../utils/api');

Page({
  data: { rooms: [] },

  onShow() {
    if (!getApp().globalData.token) {
      wx.reLaunch({ url: '/pages/login/login' });
      return;
    }
    this.load();
  },

  async load() {
    try {
      const rooms = await api.get('/api/rooms');
      this.setData({ rooms });
    } catch (e) {}
  },

  goDetail(e) {
    wx.navigateTo({ url: '/pages/booking-detail/booking-detail?id=' + e.currentTarget.dataset.id });
  },
});
