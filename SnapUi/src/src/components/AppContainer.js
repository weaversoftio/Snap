import { useEffect, useState, useCallback } from 'react';
import { styled } from '@mui/material/styles';
import Box from '@mui/material/Box';
import MuiDrawer from '@mui/material/Drawer';
import MuiAppBar from '@mui/material/AppBar';
import Toolbar from '@mui/material/Toolbar';
import List from '@mui/material/List';
import Typography from '@mui/material/Typography';
import Divider from '@mui/material/Divider';
import ListItem from '@mui/material/ListItem';
import ListItemButton from '@mui/material/ListItemButton';
import ListItemIcon from '@mui/material/ListItemIcon';
import ListItemText from '@mui/material/ListItemText';
import CheckpointIcon from '@mui/icons-material/MyLocation';
import StorageIcon from '@mui/icons-material/Storage';
import MeetingRoomIcon from '@mui/icons-material/MeetingRoom';
import ImageIcon from '@mui/icons-material/Widgets';
import SecurityIcon from '@mui/icons-material/Security';
import { useDispatch, useSelector } from 'react-redux';
import { useNavigate } from 'react-router-dom';
import { getCookie, setCookie } from '../utils/cookies';
import { authActions } from '../features/auth/authSlice';
import { Button, FormControl, MenuItem, Select, TextField, InputLabel, IconButton } from '@mui/material';
import DialogComponent from './common/Dialog';
import { useSnackbar } from 'notistack';
import Stack from '@mui/material/Stack';
import { clusterActions } from '../features/cluster/clusterSlice';
import { clusterApi } from '../api/clusterApi';
import { rbacApi } from '../api/rbacApi';
import { registryActions } from '../features/registry/registrySlice';
import UsersIcon from '@mui/icons-material/Group';
import ClusterIcon from '@mui/icons-material/Tune';
import SettingsIcon from '@mui/icons-material/Settings';
import { CloudUpload, Visibility as WatchersIcon, Webhook as SnapHookIcon, Help as HelpIcon, ContentCopy, Close, CompareArrows } from '@mui/icons-material';
import LogsSection from './common/LogsSection';
import { useLogs } from './common/LogsContext';
import HelpDialog from './common/HelpDialog';

const drawerWidth = 240;
const selectedBackgroundColor = "#6366f1";


const openedMixin = (theme) => ({
  width: drawerWidth,
  transition: theme.transitions.create('width', {
    easing: theme.transitions.easing.sharp,
    duration: theme.transitions.duration.enteringScreen,
  }),
  overflowX: 'hidden',
});

const closedMixin = (theme) => ({
  transition: theme.transitions.create('width', {
    easing: theme.transitions.easing.sharp,
    duration: theme.transitions.duration.leavingScreen,
  }),
  overflowX: 'hidden',
  width: `calc(${theme.spacing(7)} + 1px)`,
  [theme.breakpoints.up('sm')]: {
    width: `calc(${theme.spacing(8)} + 1px)`,
  },
});

const DrawerHeader = styled('div')(({ theme }) => ({
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'flex-end',
  padding: theme.spacing(0, 1),
  minHeight: '48px',
  height: '48px',
  // necessary for content to be below app bar
}));

const AppBar = styled(MuiAppBar, {
  shouldForwardProp: (prop) => prop !== 'open',
})(({ theme }) => ({
  zIndex: theme.zIndex.drawer + 1,
  background: theme.palette.mode === 'dark' 
    ? 'linear-gradient(135deg, #1e293b 0%, #0f172a 100%)'
    : 'linear-gradient(135deg, #6366f1 0%, #8b5cf6 100%)',
  borderRadius: '0 0 16px 16px',
  transition: theme.transitions.create(['width', 'margin'], {
    easing: theme.transitions.easing.sharp,
    duration: theme.transitions.duration.leavingScreen,
  }),
  variants: [
    {
      props: ({ open }) => open,
      style: {
        marginLeft: drawerWidth,
        width: `100%`,
        transition: theme.transitions.create(['width', 'margin'], {
          easing: theme.transitions.easing.sharp,
          duration: theme.transitions.duration.enteringScreen,
        }),
      },
    },
  ],
}));

const Drawer = styled(MuiDrawer, { shouldForwardProp: (prop) => prop !== 'open' })(
  ({ theme }) => ({
    width: drawerWidth,
    flexShrink: 0,
    whiteSpace: 'nowrap',
    boxSizing: 'border-box',
    variants: [
      {
        props: ({ open }) => open,
        style: {
          ...openedMixin(theme),
          '& .MuiDrawer-paper': openedMixin(theme),
        },
      },
      {
        props: ({ open }) => !open,
        style: {
          ...closedMixin(theme),
          '& .MuiDrawer-paper': closedMixin(theme),
        },
      },
    ],
  }),
);


export default function AppContainer({ children }) {
  const { enqueueSnackbar } = useSnackbar();
  const { setUsername } = useLogs();
  const navigate = useNavigate()
  const dispatch = useDispatch()
  const [open] = useState(true);
  const [switchCluster, setSwitchCluster] = useState(false);
  const [clusterName, setClusterName] = useState("");
  const [clusterUrl, setClusterUrl] = useState("");
  const [clusterToken, setClusterToken] = useState("");
  const [clusterAction, setClusterAction] = useState("");
  const [sshKey, setSshkey] = useState(null);
  const [clusterFormErrors, setClusterFormErrors] = useState({});;
  const [selectedRegistry, setSelectedRegistry] = useState("");
  const [registryRepo, setRegistryRepo] = useState("snap_images");
  const [availableRegistries, setAvailableRegistries] = useState([]);
  const [helpDialogOpen, setHelpDialogOpen] = useState(false);
  const [rbacCommand, setRbacCommand] = useState("");
  const [rbacCommandLoading, setRbacCommandLoading] = useState(false);

  const [clusterOpen, setClusterOpen] = useState(false);
  const { list: clusterList = [], selectedCluster = "", kubeAuthenticated = false, loading } = useSelector(state => state.cluster)
  const { authenticated = false, user } = useSelector(state => state.auth)
  const c_selectedCluster = getCookie("selectedCluster")

  // Fetch available registries when component mounts
  useEffect(() => {
    const fetchRegistries = async () => {
      try {
        const response = await fetch(`${window.ENV.apiUrl}/config/registry/list`);
        const data = await response.json();
        if (data.success) {
          setAvailableRegistries(data.registry_configs || []);
        }
      } catch (error) {
        console.error("Failed to fetch registries:", error);
      }
    };

    fetchRegistries();
  }, []);

  // Auto-close form when leaving the page
  useEffect(() => {
    const handleBeforeUnload = () => {
      if (clusterOpen) {
        handleClearClusterForm();
      }
    };

    window.addEventListener('beforeunload', handleBeforeUnload);

    return () => {
      window.removeEventListener('beforeunload', handleBeforeUnload);
    };
  }, [clusterOpen]);
  const token = getCookie("token")

  const handleGetClusterList = useCallback(async () => {
    dispatch(clusterActions.getList())
  }, [dispatch]);

  const handleLogout = useCallback(() => {
    dispatch(authActions.logout())
    dispatch(clusterActions.clearState())
    dispatch(registryActions.clearState())
    navigate("/")
  }, [dispatch, navigate]);

  const handleConfirmSelectCluster = useCallback(async (name) => {
    if (!authenticated || !name || !clusterList?.length) {
      return
    }
    // Prevent duplicate login calls - if login is already in progress, skip
    if (loading.login) {
      console.log("Login already in progress, skipping duplicate call");
      return;
    }
    // If there's an ongoing cluster action, wait for it to complete
    if (clusterAction) {
      setClusterAction("")
      return
    }
    // Prevent duplicate calls if cluster is already selected
    if (selectedCluster?.name === name && kubeAuthenticated) {
      return;
    }
    const cluster = clusterList.find(item => item.name === name)
    if (!cluster) {
      console.error(`Cluster ${name} not found in cluster list`)
      return
    }
    // Only navigate to cluster page if explicitly switching clusters
    if (switchCluster) {
      navigate("/")
    }
    dispatch(clusterActions.setSelectedCluster(cluster))
    dispatch(clusterActions.login(cluster))
    setCookie("selectedCluster", name)
    setSwitchCluster("")
  }, [authenticated, clusterList, clusterAction, navigate, dispatch, switchCluster, loading.login, selectedCluster?.name, kubeAuthenticated]);

  useEffect(() => {
    !token && handleLogout()
  }, [token, handleLogout])
  useEffect(() => {
    // Only trigger if we have all required data
    if (!authenticated || !c_selectedCluster || !clusterList?.length) {
      return;
    }
    
    // Only call if cluster exists in list and isn't already selected
    const cluster = clusterList.find(item => item.name === c_selectedCluster);
    if (!cluster) {
      return;
    }
    
    // Prevent duplicate calls: only trigger if cluster is not already selected
    if (selectedCluster?.name === c_selectedCluster) {
      return;
    }
    
    handleConfirmSelectCluster(c_selectedCluster);
  }, [authenticated, c_selectedCluster, clusterList, selectedCluster?.name, handleConfirmSelectCluster])

  useEffect(() => {
    if (!authenticated || !user) return
    setUsername(user.username)
    handleGetClusterList()
  }, [authenticated, user, setUsername, handleGetClusterList])

  const handleSelectCluster = (name) => {
    // If selecting the same cluster that's already selected, do nothing
    if (selectedCluster?.name === name) {
      return
    }
    // If no cluster is currently selected, auto-login immediately
    if (!selectedCluster) {
      handleConfirmSelectCluster(name)
      return
    }
    // Otherwise, show the switch dialog
    setSwitchCluster(name)
  }

  const handleRemoveCluster = async () => {
    try {
      setClusterAction("remove")
      await clusterApi.remove(switchCluster)
      handleGetClusterList()
      enqueueSnackbar("Cluster removed", { variant: "info" })
      setSwitchCluster("")
    } catch (error) {
      enqueueSnackbar("Cluster failed to remove", { variant: "error" })
    }
  }


  const handleAddCluster = async () => {
    // Clear previous errors
    setClusterFormErrors({})
    
    // Validation
    const errors = {}
    if (!clusterName.trim()) errors.name = "Cluster name is required"
    if (!clusterUrl.trim()) errors.url = "Cluster API URL is required"
    if (!clusterToken.trim()) errors.token = "Token is required"
    
    if (Object.keys(errors).length > 0) {
      setClusterFormErrors(errors)
      return
    }

    enqueueSnackbar("Creating new cluster initiated...", { variant: "info" })
    setClusterAction("create")
    
    await clusterApi.create({
      name: clusterName,
      kube_api_url: clusterUrl,
      token: clusterToken,
      registry: selectedRegistry || null,
      repo: registryRepo
    })

    if (sshKey) {
      const formData = new FormData()
      formData.append("file", sshKey)
      await clusterApi.uploadSshkey(clusterName, formData)
    }
    
    handleClearClusterForm()
    handleGetClusterList()
    enqueueSnackbar("New cluster added...", { variant: "success" })
  }

  const handleClearClusterForm = () => {
    setClusterOpen(false)
    setClusterName("")
    setClusterUrl("")
    setClusterToken("")
    setSshkey(null)
    setSelectedRegistry("")
    setRegistryRepo("snap_images")
    setRbacCommand("")
  }

  const handleCopyRBACCommand = async () => {
    try {
      setRbacCommandLoading(true);
      
      // Fetch the RBAC command from SnapAPI
      const response = await rbacApi.getRbacCommand();
      
      if (!response.success || !response.command) {
        throw new Error('Failed to get RBAC command from server');
      }

      const command = response.command;
      setRbacCommand(command);
      
      // Check if modern clipboard API is available
      if (navigator.clipboard && navigator.clipboard.writeText) {
        try {
          await navigator.clipboard.writeText(command);
          enqueueSnackbar("RBAC setup command copied to clipboard!", { variant: "success" });
        } catch (clipboardErr) {
          console.warn("Modern clipboard API failed:", clipboardErr);
          enqueueSnackbar("Command loaded. Use the copy button to copy to clipboard.", { variant: "info" });
        }
      } else {
        enqueueSnackbar("Command loaded. Use the copy button to copy to clipboard.", { variant: "info" });
      }
      
    } catch (err) {
      console.error("Error fetching RBAC command:", err);
      enqueueSnackbar("Failed to fetch RBAC command. Please try again.", { variant: "error" });
    } finally {
      setRbacCommandLoading(false);
    }
  }

  const handleCopyToClipboard = async (event) => {
    if (!rbacCommand) return;
    
    try {
      // Check if modern clipboard API is available
      if (navigator.clipboard && navigator.clipboard.writeText) {
        try {
          await navigator.clipboard.writeText(rbacCommand);
          enqueueSnackbar("RBAC setup command copied to clipboard!", { variant: "success" });
          return;
        } catch (clipboardErr) {
          console.warn("Clipboard API failed:", clipboardErr);
        }
      }

      // Fallback for older browsers
      const textArea = document.createElement("textarea");
      textArea.value = rbacCommand;
      textArea.style.position = "fixed";
      textArea.style.left = "-999999px";
      textArea.style.top = "-999999px";
      textArea.style.opacity = "0";
      textArea.style.pointerEvents = "none";
      textArea.setAttribute("readonly", "");
      document.body.appendChild(textArea);
      
      try {
        textArea.focus();
        textArea.select();
        textArea.setSelectionRange(0, 99999);
        
        const successful = document.execCommand('copy');
        if (successful) {
          enqueueSnackbar("RBAC setup command copied to clipboard!", { variant: "success" });
        } else {
          enqueueSnackbar("Please manually select and copy the text (Ctrl+C)", { variant: "info" });
        }
      } catch (execErr) {
        console.error("execCommand failed:", execErr);
        enqueueSnackbar("Please manually select and copy the text (Ctrl+C)", { variant: "info" });
      } finally {
        if (textArea && textArea.parentNode) {
          textArea.parentNode.removeChild(textArea);
        }
      }
      
    } catch (err) {
      console.error("Error copying to clipboard:", err);
      enqueueSnackbar("Copy failed. Please try again or check browser permissions.", { variant: "error" });
    }
  }

  const renderSwitchCluster = () => {
    return (
      <DialogComponent open={!!switchCluster} onClose={() => setSwitchCluster("")} paperProps={{ maxWidth: 500 }}>
        <Box gap={2} display={"flex"} flexDirection={"column"}>
          <Typography variant='h5'>Cluster management</Typography>
          <Typography variant='h6'>{`Name: ${switchCluster}`}</Typography>
          <Box display={"flex"} width={"100%"} gap={1}>
            <Button variant="contained" fullWidth onClick={() => handleConfirmSelectCluster(switchCluster)}>Switch</Button>
            <Button variant="contained" fullWidth color="error" onClick={handleRemoveCluster}>Remove</Button>
          </Box>

        </Box>
      </DialogComponent>

    )
  }


  const renderAuthenticationDetails = () => {
    return (
      <TextField
        label="Token"
        type="password"
        onChange={(e) => setClusterToken(e.target.value)}
        value={clusterToken}
        helperText={clusterFormErrors?.token}
        error={!!clusterFormErrors?.token}
      />
    )
  }

  const renderClusterForm = () => {
    return (
      <DialogComponent 
        open={clusterOpen} 
        onClose={() => {}} // Disable click-outside-to-close
        disableEscapeKeyDown={true} // Disable ESC key to close
        paperProps={{ maxWidth: 500 }}
      >
        <Box sx={{ p: 1, position: 'relative' }}>
          <Typography variant="h5" sx={{ fontWeight: 'bold', mb: 1 }}>
          Add Cluster
          </Typography>
          <IconButton
            onClick={handleClearClusterForm}
            sx={{
              position: 'absolute',
              right: 8,
              top: 8,
              color: 'text.secondary'
            }}
          >
            <Close />
          </IconButton>
        </Box>
        <Box gap={2} display={"flex"} flexDirection={"column"}>
          <TextField
            label="Cluster Name"
            onChange={(e) => setClusterName(e.target.value)}
            value={clusterName}
            helperText={clusterFormErrors?.name}
            error={!!clusterFormErrors?.name}
          />
          <TextField
            label="Cluster Api Url"
            onChange={(e) => setClusterUrl(e.target.value)}
            value={clusterUrl}
            helperText={clusterFormErrors?.url}
            error={!!clusterFormErrors?.url}
          />

          {/* RBAC Setup Command - moved before Token */}
          <Button 
            variant="outlined" 
            sx={{ marginBottom: "8px" }} 
            startIcon={<ContentCopy />}
            onClick={handleCopyRBACCommand}
            disabled={rbacCommandLoading}
          >
            {rbacCommandLoading ? "Loading..." : "Get RBAC Setup Command"}
          </Button>
          
          {rbacCommand && (
            <Box sx={{ mt: 2 }}>
              <Typography variant="body2" sx={{ mb: 1, fontWeight: 'medium' }}>
                RBAC Setup Command:
              </Typography>
              <TextField
                multiline
                rows={6}
                value={rbacCommand}
                variant="outlined"
                fullWidth
                InputProps={{
                  readOnly: true,
                  style: { 
                    fontFamily: 'monospace', 
                    fontSize: '12px',
                    backgroundColor: '#f5f5f5',
                    cursor: 'text',
                    userSelect: 'text',
                    WebkitUserSelect: 'text',
                    MozUserSelect: 'text',
                    msUserSelect: 'text'
                  }
                }}
                sx={{ 
                  mb: 1,
                  '& .MuiInputBase-input': {
                    cursor: 'text',
                    userSelect: 'text',
                    WebkitUserSelect: 'text',
                    MozUserSelect: 'text',
                    msUserSelect: 'text'
                  }
                }}
                onClick={(e) => {
                  // Select all text when clicked
                  e.target.select();
                }}
              />
              <Box sx={{ display: 'flex', gap: 1 }}>
                <Button 
                  variant="contained" 
                  size="small"
                  startIcon={<ContentCopy />}
                  onClick={(event) => handleCopyToClipboard(event)}
                >
                  Copy to Clipboard
                </Button>
                <Button 
                  variant="outlined" 
                  size="small"
                  onClick={() => {
                    const textArea = document.querySelector('textarea[readonly]');
                    if (textArea) {
                      textArea.focus();
                      textArea.select();
                      enqueueSnackbar("Text selected. Press Ctrl+C (Cmd+C on Mac) to copy.", { variant: "info" });
                    }
                  }}
                >
                  Select All
                </Button>
              </Box>
            </Box>
          )}

          {/* Token input - moved after RBAC command */}
          {renderAuthenticationDetails()}
          
          <Button variant="outlined" component="label" sx={{ width: 200 }} startIcon={<CloudUpload />}>
            Upload SSH Key
            <input
              type="file"
              accept="*"
              hidden
              onChange={(e) => setSshkey(e.target.files[0])}
            />
          </Button>
          {sshKey && <Typography variant="body2">{sshKey.name}</Typography>}
          
          {/* Registry Selection */}
          <FormControl sx={{ minWidth: 120 }} fullWidth variant='outlined'>
            <InputLabel>Registry (Optional)</InputLabel>
            <Select
              value={selectedRegistry}
              onChange={(e) => setSelectedRegistry(e.target.value)}
              label="Registry (Optional)"
            >
              <MenuItem value="">None (No cluster cache will be created)</MenuItem>
              {availableRegistries.map((registry) => (
                <MenuItem key={registry.name} value={registry.name}>
                  {registry.name} ({registry.registry_config_details.registry})
                </MenuItem>
              ))}
            </Select>
          </FormControl>
          
          {selectedRegistry && (
            <TextField
              label="Repository Name"
              onChange={(e) => setRegistryRepo(e.target.value)}
              value={registryRepo}
              helperText="Repository name for storing checkpoint images"
            />
          )}
          
          <Button variant="contained" onClick={handleAddCluster}>Submit</Button>
        </Box>
      </DialogComponent>
    )
  }

  const isSelected = (path) => {
    return window.location.pathname === path
  }

  // Helper function to decode JWT token and get auth_method
  const getAuthMethodFromToken = () => {
    try {
      const token = getCookie("token");
      if (!token) return "Local User";
      // JWT tokens have 3 parts: header.payload.signature
      const parts = token.split('.');
      if (parts.length !== 3) return "Local User";
      
      // Decode base64url (JWT uses base64url, not standard base64)
      let payload = parts[1];
      // Add padding if needed
      payload += '='.repeat((4 - payload.length % 4) % 4);
      // Replace URL-safe characters
      payload = payload.replace(/-/g, '+').replace(/_/g, '/');
      const decoded = JSON.parse(atob(payload));
      return decoded.auth_method === 'ad' ? 'Domain User' : 'Local User';
    } catch (e) {
      return 'Local User';
    }
  };

  const renderDrawer = () => {
    if (!authenticated) return
    
    // Section 2: Cluster-dependent menu items (only show when cluster is selected)
    const clusterMenu = [
      { text: "Pods", path: "/pods", Icon: ImageIcon },
      { text: "Checkpoints", path: "/checkpoints", Icon: CheckpointIcon },
      { text: "Compare CP", path: "/checkpoints/compare", Icon: CompareArrows },
      { text: "Secrets", path: "/secrets", Icon: SecurityIcon },
      { text: "Watchers", path: "/snapwatcher", Icon: WatchersIcon },
      { text: "Hooks", path: "/snaphook", Icon: SnapHookIcon },
    ]

    // Section 3: App-level menu items (always show when authenticated)
    const appMenu = [
      { text: "Registry", path: "/registry", Icon: StorageIcon },
      { text: "Users", path: "/users", Icon: UsersIcon },
      { text: "Settings", path: "/settings", Icon: SettingsIcon },
    ]

    const showClusterNavigation = kubeAuthenticated && selectedCluster

    return (
      <Drawer 
        variant="permanent" 
        open={open} 
        sx={{ 
          height: 'calc(100vh - 48px)',
          marginTop: '48px',
          '& .MuiDrawer-paper': {
            height: 'calc(100vh - 48px)',
            marginTop: '48px',
            overflowY: 'auto',
            overflowX: 'hidden',
            borderRight: (theme) => theme.palette.mode === 'dark' 
              ? '1px solid rgba(255, 255, 255, 0.08)' 
              : '1px solid rgba(0, 0, 0, 0.08)',
            background: (theme) => theme.palette.mode === 'dark'
              ? 'linear-gradient(180deg, #1e293b 0%, #0f172a 100%)'
              : 'linear-gradient(180deg, #ffffff 0%, #f8fafc 100%)',
            boxShadow: (theme) => theme.palette.mode === 'dark'
              ? '4px 0 12px rgba(0, 0, 0, 0.3)'
              : '4px 0 12px rgba(0, 0, 0, 0.04)',
          }
        }}
      >
        {/* Section 2: Cluster-dependent menu items */}
        {showClusterNavigation && (
          <>
            <Box 
              sx={{ 
                px: 2.5, 
                py: 1.5, 
                flexShrink: 0,
                background: (theme) => theme.palette.mode === 'dark'
                  ? 'rgba(99, 102, 241, 0.08)'
                  : 'rgba(99, 102, 241, 0.04)',
                borderLeft: '3px solid',
                borderColor: 'primary.main',
                marginBottom: 1,
              }}
            >
              <Typography 
                variant="overline" 
                sx={{ 
                  fontSize: '0.7rem', 
                  fontWeight: 700, 
                  color: 'primary.main', 
                  letterSpacing: '0.1em',
                  textTransform: 'uppercase',
                }}
              >
                Cluster Operations
              </Typography>
            </Box>
            <List sx={{ flexShrink: 0, px: 1.5, py: 0.5 }}>
              {clusterMenu.map(({ text, path, Icon }) => {
                const selected = isSelected(path);
                return (
                  <ListItem key={text} disablePadding sx={{ display: 'block', mb: 0.5 }}>
                    <ListItemButton
                      onClick={() => navigate(path)}
                      selected={selected}
                      sx={{
                        minHeight: 44,
                        px: 2,
                        py: 1,
                        borderRadius: 2,
                        position: 'relative',
                        transition: 'all 0.2s cubic-bezier(0.4, 0, 0.2, 1)',
                        ...(open ? { justifyContent: 'initial' } : { justifyContent: 'center' }),
                        ...(selected ? {
                          background: 'linear-gradient(135deg, #6366f1 0%, #8b5cf6 100%)',
                          color: 'white',
                          boxShadow: '0px 2px 8px rgba(99, 102, 241, 0.3)',
                        } : {
                          '&:hover': {
                            background: (theme) => theme.palette.mode === 'dark'
                              ? 'rgba(99, 102, 241, 0.15)'
                              : 'rgba(99, 102, 241, 0.08)',
                            transform: 'translateX(4px)',
                            boxShadow: '0px 2px 4px rgba(99, 102, 241, 0.1)',
                          },
                        }),
                      }}
                    >
                      <ListItemIcon
                        sx={{
                          minWidth: 0,
                          justifyContent: 'center',
                          ...(open ? { mr: 2.5 } : { mr: 'auto' }),
                          color: selected ? 'white' : 'inherit',
                          transition: 'color 0.2s cubic-bezier(0.4, 0, 0.2, 1)',
                        }}
                      >
                        <Icon sx={{ fontSize: '1.4rem' }} />
                      </ListItemIcon>
                      <ListItemText
                        primary={text}
                        sx={{
                          opacity: open ? 1 : 0,
                          transition: 'opacity 0.2s',
                          '& .MuiTypography-root': {
                            fontWeight: selected ? 600 : 500,
                            fontSize: '0.9375rem',
                            letterSpacing: '0.01em',
                          },
                        }}
                      />
                    </ListItemButton>
                  </ListItem>
                );
              })}
            </List>
          </>
        )}
        
        {/* Section 3: App-level menu items */}
        <Box 
          sx={{ 
            px: 2.5, 
            py: 1.5, 
            flexShrink: 0,
            background: (theme) => theme.palette.mode === 'dark'
              ? 'rgba(99, 102, 241, 0.08)'
              : 'rgba(99, 102, 241, 0.04)',
            borderLeft: '3px solid',
            borderColor: 'primary.main',
            marginTop: showClusterNavigation ? 2 : 0,
            marginBottom: 1,
          }}
        >
          <Typography 
            variant="overline" 
            sx={{ 
              fontSize: '0.7rem', 
              fontWeight: 700, 
              color: 'primary.main', 
              letterSpacing: '0.1em',
              textTransform: 'uppercase',
            }}
          >
            Application
          </Typography>
        </Box>
        <Box sx={{ display: 'flex', flexDirection: 'column', flexGrow: 1, overflow: 'hidden' }}>
          <List sx={{ flexGrow: 1, overflowY: 'auto', px: 1.5, py: 0.5 }}>
            {appMenu.map(({ text, path, Icon }) => {
              const selected = isSelected(path);
              return (
                <ListItem key={text} disablePadding sx={{ display: 'block', mb: 0.5 }}>
                  <ListItemButton
                    onClick={() => navigate(path)}
                    selected={selected}
                    sx={{
                      minHeight: 44,
                      px: 2,
                      py: 1,
                      borderRadius: 2,
                      position: 'relative',
                      transition: 'all 0.2s cubic-bezier(0.4, 0, 0.2, 1)',
                      ...(open ? { justifyContent: 'initial' } : { justifyContent: 'center' }),
                      ...(selected ? {
                        background: 'linear-gradient(135deg, #6366f1 0%, #8b5cf6 100%)',
                        color: 'white',
                        boxShadow: '0px 2px 8px rgba(99, 102, 241, 0.3)',
                      } : {
                        '&:hover': {
                          background: (theme) => theme.palette.mode === 'dark'
                            ? 'rgba(99, 102, 241, 0.15)'
                            : 'rgba(99, 102, 241, 0.08)',
                          transform: 'translateX(4px)',
                          boxShadow: '0px 2px 4px rgba(99, 102, 241, 0.1)',
                        },
                      }),
                    }}
                  >
                    <ListItemIcon
                      sx={{
                        minWidth: 0,
                        justifyContent: 'center',
                        ...(open ? { mr: 2.5 } : { mr: 'auto' }),
                        color: selected ? 'white' : 'inherit',
                        transition: 'color 0.2s cubic-bezier(0.4, 0, 0.2, 1)',
                      }}
                    >
                      <Icon sx={{ fontSize: '1.4rem' }} />
                    </ListItemIcon>
                    <ListItemText
                      primary={text}
                      sx={{
                        opacity: open ? 1 : 0,
                        transition: 'opacity 0.2s',
                        '& .MuiTypography-root': {
                          fontWeight: selected ? 600 : 500,
                          fontSize: '0.9375rem',
                          letterSpacing: '0.01em',
                        },
                      }}
                    />
                  </ListItemButton>
                </ListItem>
              );
            })}
          </List>
          <Box sx={{ pt: 2, pb: 1.5, px: 1.5, borderTop: (theme) => theme.palette.mode === 'dark' ? '1px solid rgba(255, 255, 255, 0.08)' : '1px solid rgba(0, 0, 0, 0.08)' }}>
            <ListItem key={"Logout"} disablePadding sx={{ display: 'block' }} onClick={handleLogout}>
              <ListItemButton
                sx={{
                  minHeight: 44,
                  px: 2,
                  py: 1,
                  borderRadius: 2,
                  transition: 'all 0.2s cubic-bezier(0.4, 0, 0.2, 1)',
                  ...(open ? { justifyContent: 'initial' } : { justifyContent: 'center' }),
                  color: (theme) => theme.palette.mode === 'dark' ? '#ef4444' : '#dc2626',
                  '&:hover': {
                    background: (theme) => theme.palette.mode === 'dark'
                      ? 'rgba(239, 68, 68, 0.15)'
                      : 'rgba(220, 38, 38, 0.08)',
                    transform: 'translateX(4px)',
                    boxShadow: '0px 2px 4px rgba(220, 38, 38, 0.1)',
                  },
                }}
              >
                <ListItemIcon 
                  sx={{
                    minWidth: 0,
                    justifyContent: 'center',
                    ...(open ? { mr: 2.5 } : { mr: 'auto' }),
                    color: 'inherit',
                    transition: 'color 0.2s cubic-bezier(0.4, 0, 0.2, 1)',
                  }}
                >
                  <MeetingRoomIcon sx={{ fontSize: '1.4rem' }} />
                </ListItemIcon>
                <ListItemText
                  primary={"Logout"}
                  sx={{
                    opacity: open ? 1 : 0,
                    transition: 'opacity 0.2s',
                    '& .MuiTypography-root': {
                      fontWeight: 600,
                      fontSize: '0.9375rem',
                      letterSpacing: '0.01em',
                    },
                  }}
                />
              </ListItemButton>
            </ListItem>
          </Box>
        </Box>
      </Drawer>
    )
  }

  return (
    <>

      <Box sx={{ display: 'flex' }}>
        {renderSwitchCluster()}
        {renderClusterForm()}
        {authenticated && <AppBar position="fixed" open={open} component="nav">
          <Toolbar sx={{ minHeight: '48px !important', py: 0.5 }}>
            <Stack direction="row" spacing={1.5} sx={{ alignItems: "center", justifyContent: "space-between", flexGrow: 1 }}>
              <Stack direction="row" spacing={1.5} sx={{ alignItems: "center" }}>
                <Box
                  component="img"
                  sx={{
                    height: 36,
                    filter: 'brightness(0) invert(1)',
                    transition: 'all 0.3s cubic-bezier(0.4, 0, 0.2, 1)',
                    '&:hover': {
                      transform: 'scale(1.05)',
                    },
                  }}
                  alt="SNAP logo"
                  src="/logo.png"
                />
                <Typography 
                  variant="h6" 
                  noWrap 
                  component="div" 
                  sx={{ 
                    fontSize: '1.1rem', 
                    fontWeight: 600,
                    color: 'white',
                    letterSpacing: '0.01em',
                  }}
                >
                  Dashboard
                </Typography>
                {authenticated && user && (
                  <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5, ml: 1 }}>
                    <Typography variant="body2" sx={{ fontWeight: 'bold', fontSize: '0.875rem', whiteSpace: 'nowrap' }}>
                      Cluster:
                    </Typography>
                    <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
                      <FormControl sx={{ minWidth: 120, maxWidth: 180 }} size="small" variant='outlined'>
                        <Select
                          value={selectedCluster?.name || "default"}
                          onChange={(e) => handleSelectCluster(e.target.value)}
                          sx={{ 
                            height: '32px',
                            backgroundColor: 'rgba(255, 255, 255, 0.1)',
                            color: 'white',
                            '& .MuiSelect-select': {
                              py: 0.5,
                              fontSize: '0.875rem',
                              color: 'white'
                            },
                            '& .MuiOutlinedInput-notchedOutline': {
                              borderColor: 'rgba(255, 255, 255, 0.3)'
                            },
                            '&:hover .MuiOutlinedInput-notchedOutline': {
                              borderColor: 'rgba(255, 255, 255, 0.5)'
                            },
                            '& .MuiSvgIcon-root': {
                              color: 'white'
                            }
                          }}
                        >
                          <MenuItem onClick={() => setClusterOpen(true)} value={selectedCluster?.name || "default"} style={{ fontStyle: "italic" }}>Add Cluster</MenuItem>
                          {clusterList.map(item => <MenuItem value={item.name} key={item.name}>{item.name}</MenuItem>)}
                        </Select>
                      </FormControl>
                      <Button 
                        color="inherit" 
                        onClick={() => navigate("/")} 
                        sx={{ 
                          backgroundColor: isSelected("/") ? selectedBackgroundColor : "rgba(255, 255, 255, 0.1)", 
                          minWidth: '32px',
                          width: '32px',
                          height: '32px',
                          p: 0,
                          flexShrink: 0,
                          '&:hover': {
                            backgroundColor: isSelected("/") ? selectedBackgroundColor : "rgba(255, 255, 255, 0.2)"
                          }
                        }}
                      >
                        <ClusterIcon sx={{ color: isSelected("/") ? "white" : "white", fontSize: '1.2rem' }} />
                      </Button>
                    </Box>
                  </Box>
                )}
              </Stack>
              <Stack direction="row" spacing={1.5} sx={{ alignItems: "center" }}>
                {authenticated && user && (
                  <Stack direction="column" spacing={0} sx={{ alignItems: "flex-start", mr: 1 }}>
                    <Typography variant="body2" sx={{ fontSize: '0.875rem', lineHeight: 1.2 }}>
                      <Box component="span" sx={{ fontWeight: 'bold', minWidth: '45px', display: 'inline-block' }}>User:</Box> {user.username || user.name || 'Unknown'}
                    </Typography>
                    <Typography variant="body2" sx={{ fontSize: '0.875rem', lineHeight: 1.2 }}>
                      <Box component="span" sx={{ fontWeight: 'bold', minWidth: '45px', display: 'inline-block' }}>Type:</Box> {getAuthMethodFromToken()}
                    </Typography>
                  </Stack>
                )}
                <Button
                  color="inherit"
                  onClick={() => setHelpDialogOpen(true)}
                  startIcon={<HelpIcon />}
                  sx={{ 
                    fontSize: '0.875rem',
                    color: 'white',
                    '&:hover': {
                      backgroundColor: 'rgba(255, 255, 255, 0.1)',
                    },
                  }}
                  size="small"
                >
                  Help
                </Button>
              </Stack>
            </Stack>
          </Toolbar>
        </AppBar>}
        {renderDrawer()}
        <Box component="main" sx={{ flexGrow: 1, p: 3, backgroundColor: (theme) => theme.palette.mode === 'dark' ? theme.palette.background.default : "#f5f5f5", position: "relative", paddingBottom: "80px" }} width={"100%"} height={"100%"} minHeight={"100vh"}>
          <DrawerHeader />
          {children}
        </Box>
        {authenticated && <LogsSection />}
        <HelpDialog 
          open={helpDialogOpen} 
          onClose={() => setHelpDialogOpen(false)} 
        />
      </Box>
    </>
  );
}
