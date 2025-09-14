import { api } from '../utils/api';

export const watcherApi = {
  // Get all watchers for a cluster
  getWatchers: async (clusterName) => {
    try {
      const response = await api.get(`/operator/status`);
      return response.data;
    } catch (error) {
      console.error('Error fetching watchers:', error);
      throw error;
    }
  },

  // Start a watcher
  startWatcher: async (clusterName, clusterConfig) => {
    try {
      const response = await api.post('/operator/start', {
        cluster_name: clusterName,
        cluster_config: clusterConfig
      });
      return response.data;
    } catch (error) {
      console.error('Error starting watcher:', error);
      throw error;
    }
  },

  // Stop a watcher
  stopWatcher: async () => {
    try {
      const response = await api.post('/operator/stop');
      return response.data;
    } catch (error) {
      console.error('Error stopping watcher:', error);
      throw error;
    }
  },

  // Get watcher status
  getWatcherStatus: async () => {
    try {
      const response = await api.get('/operator/status');
      return response.data;
    } catch (error) {
      console.error('Error getting watcher status:', error);
      throw error;
    }
  }
};
