import React, { useState, useEffect } from 'react';
import { useSelector } from 'react-redux';
import { Box, Typography, Tabs, Tab, Paper } from '@mui/material';
import SnapHookManagement from '../SnapHook/SnapHookManagement';
import SnapHookStatus from '../SnapHook/SnapHookStatus';

function TabPanel({ children, value, index, ...other }) {
  return (
    <div
      role="tabpanel"
      hidden={value !== index}
      id={`snaphook-tabpanel-${index}`}
      aria-labelledby={`snaphook-tab-${index}`}
      {...other}
    >
      {value === index && (
        <Box sx={{ p: 3 }}>
          {children}
        </Box>
      )}
    </div>
  );
}

function a11yProps(index) {
  return {
    id: `snaphook-tab-${index}`,
    'aria-controls': `snaphook-tabpanel-${index}`,
  };
}

const SnapHookScreen = () => {
  const [tabValue, setTabValue] = useState(0);
  const [selectedHook, setSelectedHook] = useState(null);
  
  const { selectedCluster } = useSelector(state => state.cluster);

  const handleTabChange = (event, newValue) => {
    setTabValue(newValue);
  };

  const handleHookSelect = (hookName) => {
    setSelectedHook(hookName);
    setTabValue(1); // Switch to status tab
  };

  if (!selectedCluster) {
    return (
      <Box sx={{ p: 3 }}>
        <Typography variant="h4" gutterBottom>
          SnapHook Management
        </Typography>
        <Typography variant="body1" color="text.secondary">
          Please select a cluster to manage SnapHook webhooks.
        </Typography>
      </Box>
    );
  }

  return (
    <Box sx={{ width: '100%' }}>
      <Typography variant="h4" gutterBottom sx={{ mb: 3 }}>
        SnapHook Management
      </Typography>
      
      <Typography variant="body1" color="text.secondary" sx={{ mb: 3 }}>
        Manage SnapHook webhooks for cluster: <strong>{selectedCluster.name}</strong>
      </Typography>

      <Paper sx={{ width: '100%' }}>
        <Box sx={{ borderBottom: 1, borderColor: 'divider' }}>
          <Tabs value={tabValue} onChange={handleTabChange} aria-label="snaphook tabs">
            <Tab label="Management" {...a11yProps(0)} />
            <Tab 
              label="Status" 
              {...a11yProps(1)} 
              disabled={!selectedHook}
            />
          </Tabs>
        </Box>
        
        <TabPanel value={tabValue} index={0}>
          <SnapHookManagement 
            clusterName={selectedCluster.name}
            clusterConfig={selectedCluster}
            onHookSelect={handleHookSelect}
          />
        </TabPanel>
        
        <TabPanel value={tabValue} index={1}>
          {selectedHook ? (
            <SnapHookStatus hookName={selectedHook} />
          ) : (
            <Typography variant="body1" color="text.secondary">
              Select a SnapHook from the Management tab to view its status.
            </Typography>
          )}
        </TabPanel>
      </Paper>
    </Box>
  );
};

export default SnapHookScreen;
