const api = require('../../utils/api');

const STATUS_TEXT = {
  submitted: '待受理', assigned: '已分配', in_progress: '维修中', done: '已完成', closed: '已关闭',
};
const STATUS_CLASS = {
  submitted: 'tag-orange', assigned: 'tag-blue', in_progress: 'tag-blue', done: 'tag-green', closed: 'tag-gray',
};

Page({
  data: {
    scope: 'mine',
    isAdmin: false,
    list: [],
    rooms: [],
    showForm: false,
    form: { room_id: null, roomName: '', device_name: '', description: '', images: [] },
    statusText: STATUS_TEXT,
    statusClass: STATUS_CLASS,
  },

  onShow() {
    const app = getApp();
    if (!app.globalData.token) { wx.reLaunch({ url: '/pages/login/login' }); return; }
    this.setData({ isAdmin: app.globalData.userInfo && app.globalData.userInfo.role === 'admin' });
    this.load();
  },

  async load() {
    try {
      const list = await api.get('/api/repairs', { scope: this.data.scope });
      this.setData({ list });
    } catch (e) {}
  },

  switchScope(e) {
    this.setData({ scope: e.currentTarget.dataset.s }, () => this.load());
  },

  goDetail(e) {
    wx.navigateTo({ url: '/pages/repair-detail/repair-detail?id=' + e.currentTarget.dataset.id });
  },

  async openForm() {
    try {
      const rooms = await api.get('/api/rooms');
      this.setData({ rooms, showForm: true, form: { room_id: null, roomName: '', device_name: '', description: '', images: [] } });
    } catch (e) {}
  },
  closeForm() { this.setData({ showForm: false }); },

  onRoom(e) {
    const room = this.data.rooms[e.detail.value];
    this.setData({ 'form.room_id': room.id, 'form.roomName': room.name });
  },
  onInput(e) {
    this.setData({ ['form.' + e.currentTarget.dataset.k]: e.detail.value });
  },
  chooseImg() {
    wx.chooseImage({
      count: 3,
      success: (res) => {
        // 演示：直接用本地临时路径占位；生产应先上传到对象存储再存 URL
        this.setData({ 'form.images': this.data.form.images.concat(res.tempFilePaths) });
      },
    });
  },

  async submit() {
    const f = this.data.form;
    if (!f.room_id || !f.device_name || !f.description) {
      wx.showToast({ title: '请填写完整', icon: 'none' });
      return;
    }
    try {
      await api.post('/api/repairs', {
        room_id: f.room_id, device_name: f.device_name,
        description: f.description, images: f.images,
      });
      wx.showToast({ title: '已提交', icon: 'success' });
      this.setData({ showForm: false });
      this.load();
    } catch (e) {}
  },
});
