const api = require('../../utils/api');

function fmtDate(d) {
  const p = (n) => (n < 10 ? '0' + n : '' + n);
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}`;
}
function hhmm(iso) {
  // 后端返回 naive UTC，按时段标签直接取时分
  const t = iso.split('T')[1] || '';
  return t.slice(0, 5);
}

Page({
  data: {
    roomId: null,
    room: {},
    today: fmtDate(new Date()),
    date: fmtDate(new Date()),
    slots: [],
    selStart: null, // 选中起始索引
    selEnd: null,
    selText: '',
    purpose: '',
  },

  onLoad(q) {
    this.setData({ roomId: Number(q.id) });
    this.loadRoom();
    this.loadSlots();
  },

  async loadRoom() {
    try {
      const room = await api.get('/api/rooms/' + this.data.roomId);
      this.setData({ room });
    } catch (e) {}
  },

  async loadSlots() {
    try {
      const res = await api.get(`/api/rooms/${this.data.roomId}/availability`, { date: this.data.date });
      const slots = res.slots.map((s) => ({
        ...s,
        timeLabel: hhmm(s.start),
        selected: false,
      }));
      this.setData({ slots, selStart: null, selEnd: null, selText: '', purpose: '' });
    } catch (e) {}
  },

  onDate(e) {
    this.setData({ date: e.detail.value }, () => this.loadSlots());
  },

  onPurpose(e) {
    this.setData({ purpose: e.detail.value });
  },

  onSlot(e) {
    const idx = Number(e.currentTarget.dataset.idx);
    const slots = this.data.slots;
    if (!slots[idx].available) return;

    let { selStart, selEnd } = this.data;
    if (selStart === null || selEnd !== null) {
      // 开始新的选择
      selStart = idx;
      selEnd = null;
    } else {
      // 设定结束；要求区间连续且全部空闲
      const [a, b] = idx >= selStart ? [selStart, idx] : [idx, selStart];
      for (let i = a; i <= b; i++) {
        if (!slots[i].available) {
          wx.showToast({ title: '所选区间含占用时段', icon: 'none' });
          return;
        }
      }
      selStart = a;
      selEnd = b;
    }

    const a = selStart;
    const b = selEnd === null ? selStart : selEnd;
    slots.forEach((s, i) => (s.selected = i >= a && i <= b));
    const selText = `${slots[a].timeLabel} - ${hhmm(slots[b].end)}`;
    this.setData({ slots, selStart, selEnd, selText });
  },

  async submit() {
    const { slots, selStart, selEnd } = this.data;
    const a = selStart;
    const b = selEnd === null ? selStart : selEnd;
    try {
      await api.post('/api/bookings', {
        room_id: this.data.roomId,
        start_time: slots[a].start,
        end_time: slots[b].end,
        purpose: this.data.purpose,
      });
      wx.showToast({ title: '预约成功', icon: 'success' });
      this.loadSlots();
    } catch (e) {}
  },
});
