export const createNotificationSlice = (set, get) => ({
  notifications: [],
  
  addNotification: (message, type = "info", duration = 3000) => {
    const id = Date.now().toString();
    const notification = { id, message, type, duration };
    
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
