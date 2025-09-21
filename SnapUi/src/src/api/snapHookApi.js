import { api } from '../utils/api';

export const snapHookApi = {
  // Get all SnapHooks
  getSnapHooks: async () => {
    try {
      const response = await api.get(`/snaphooks`);
      return response.data;
    } catch (error) {
      console.error('Error fetching SnapHooks:', error);
      throw error;
    }
  },

  // Create a new SnapHook
  createSnapHook: async (hookData) => {
    try {
      const response = await api.post('/snaphook', hookData);
      return response.data;
    } catch (error) {
      console.error('Error creating SnapHook:', error);
      throw error;
    }
  },

  // Update a SnapHook
  updateSnapHook: async (hookName, hookData) => {
    try {
      const response = await api.put(`/snaphook/${hookName}`, hookData);
      return response.data;
    } catch (error) {
      console.error('Error updating SnapHook:', error);
      throw error;
    }
  },

  // Delete a SnapHook
  deleteSnapHook: async (hookName) => {
    try {
      const response = await api.delete(`/snaphook/${hookName}`);
      return response.data;
    } catch (error) {
      console.error('Error deleting SnapHook:', error);
      throw error;
    }
  },

  // Start a SnapHook
  startSnapHook: async (hookName) => {
    try {
      const response = await api.post(`/snaphook/${hookName}/start`);
      return response.data;
    } catch (error) {
      console.error('Error starting SnapHook:', error);
      throw error;
    }
  },

  // Stop a SnapHook
  stopSnapHook: async (hookName) => {
    try {
      const response = await api.post(`/snaphook/${hookName}/stop`);
      return response.data;
    } catch (error) {
      console.error('Error stopping SnapHook:', error);
      throw error;
    }
  },

  // Get SnapHook status
  getSnapHookStatus: async (hookName) => {
    try {
      const response = await api.get(`/snaphook/${hookName}/status`);
      return response.data;
    } catch (error) {
      console.error('Error getting SnapHook status:', error);
      throw error;
    }
  },

  // Renew SnapHook certificates
  renewSnapHookCertificates: async (hookName) => {
    try {
      const response = await api.post(`/snaphook/${hookName}/renew-certificates`);
      return response.data;
    } catch (error) {
      console.error('Error renewing SnapHook certificates:', error);
      throw error;
    }
  },

  // Test SnapHook connectivity
  testSnapHookConnectivity: async (hookName) => {
    try {
      const response = await api.get(`/snaphook/${hookName}/test-connectivity`);
      return response.data;
    } catch (error) {
      console.error('Error testing SnapHook connectivity:', error);
      throw error;
    }
  }
};
