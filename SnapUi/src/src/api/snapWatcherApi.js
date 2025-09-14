import { api } from '../utils/api';

export const snapWatcherApi = {
  // Get all SnapWatchers for a cluster
  getSnapWatchers: async (clusterName) => {
    try {
      const response = await api.get(`/operator/snapwatchers/${clusterName}`);
      return response.data;
    } catch (error) {
      console.error('Error fetching SnapWatchers:', error);
      throw error;
    }
  },

  // Create a new SnapWatcher
  createSnapWatcher: async (watcherData) => {
    try {
      const response = await api.post('/operator/snapwatcher', watcherData);
      return response.data;
    } catch (error) {
      console.error('Error creating SnapWatcher:', error);
      throw error;
    }
  },

  // Update a SnapWatcher
  updateSnapWatcher: async (watcherId, watcherData) => {
    try {
      const response = await api.put(`/operator/snapwatcher/${watcherId}`, watcherData);
      return response.data;
    } catch (error) {
      console.error('Error updating SnapWatcher:', error);
      throw error;
    }
  },

  // Delete a SnapWatcher
  deleteSnapWatcher: async (watcherId) => {
    try {
      const response = await api.delete(`/operator/snapwatcher/${watcherId}`);
      return response.data;
    } catch (error) {
      console.error('Error deleting SnapWatcher:', error);
      throw error;
    }
  },

  // Start a SnapWatcher
  startSnapWatcher: async (watcherId) => {
    try {
      const response = await api.post(`/operator/snapwatcher/${watcherId}/start`);
      return response.data;
    } catch (error) {
      console.error('Error starting SnapWatcher:', error);
      throw error;
    }
  },

  // Stop a SnapWatcher
  stopSnapWatcher: async (watcherId) => {
    try {
      const response = await api.post(`/operator/snapwatcher/${watcherId}/stop`);
      return response.data;
    } catch (error) {
      console.error('Error stopping SnapWatcher:', error);
      throw error;
    }
  },

  // Get SnapWatcher status
  getSnapWatcherStatus: async (watcherId) => {
    try {
      const response = await api.get(`/operator/snapwatcher/${watcherId}/status`);
      return response.data;
    } catch (error) {
      console.error('Error getting SnapWatcher status:', error);
      throw error;
    }
  },

  // Get SnapWatcher logs
  getSnapWatcherLogs: async (watcherId) => {
    try {
      const response = await api.get(`/operator/snapwatcher/${watcherId}/logs`);
      return response.data;
    } catch (error) {
      console.error('Error getting SnapWatcher logs:', error);
      throw error;
    }
  }
};
