export const createNotificationSlice = (set, get) => ({
  notifications: [],
  
  // meta: { teamId, action } 등 액션 페이로드 (선택)
  addNotification: (message, type = "info", meta = null, duration = 6000) => {
    const id = Date.now().toString();
    const notification = { id, message, type, meta, duration };

    set((state) => ({
      notifications: [notification, ...state.notifications]
    }));

    if (duration > 0) {
      setTimeout(() => {
        get().removeNotification(id);
      }, duration);
    }
  },

  removeNotification: (id) => {
    set((state) => ({
      notifications: state.notifications.filter((n) => n.id !== id)
    }));
  }
});
