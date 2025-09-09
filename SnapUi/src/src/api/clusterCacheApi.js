import { api } from '../utils/api';

export const clusterCacheApi = {
  // Get cluster cache for a specific cluster
  get: async (clusterName) => {
    const response = await api.get(`/config/clusterCache/get/${clusterName}`);
    return response.data;
  },

  // Update cluster cache
  update: async (clusterCacheData) => {
    const response = await api.put('/config/clusterCache/update', clusterCacheData);
    return response.data;
  },

  // Create cluster cache
  create: async (clusterCacheData) => {
    const response = await api.post('/config/clusterCache/create', clusterCacheData);
    return response.data;
  },

  // List all cluster caches
  list: async () => {
    const response = await api.get('/config/clusterCache/list');
    return response.data;
  },

  // Delete cluster cache
  delete: async (clusterName) => {
    const response = await api.delete('/config/clusterCache/delete', {
      data: { cluster: clusterName }
    });
    return response.data;
  }
};
