import { useEffect, useState, useCallback } from 'react';
import { styled } from '@mui/material/styles';
import Box from '@mui/material/Box';
import MuiDrawer from '@mui/material/Drawer';
import MuiAppBar from '@mui/material/AppBar';
import Toolbar from '@mui/material/Toolbar';
import List from '@mui/material/List';
import CssBaseline from '@mui/material/CssBaseline';
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
import { Button, FormControl, MenuItem, Select, TextField, InputLabel } from '@mui/material';
import DialogComponent from './common/Dialog';
import { useSnackbar } from 'notistack';
import Stack from '@mui/material/Stack';
import { clusterActions } from '../features/cluster/clusterSlice';
import { clusterApi } from '../api/clusterApi';
import { rbacApi } from '../api/rbacApi';
import { registryActions } from '../features/registry/registrySlice';
import UsersIcon from '@mui/icons-material/Group';
import ClusterIcon from '@mui/icons-material/Tune';
import { CloudUpload, Visibility as WatchersIcon, Webhook as SnapHookIcon, Help as HelpIcon, ContentCopy } from '@mui/icons-material';
import LogsSection from './common/LogsSection';
import { useLogs } from './common/LogsContext';
import HelpDialog from './common/HelpDialog';

const drawerWidth = 240;
const selectedBackgroundColor = "rgba(36, 143, 231, 1)";


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
  // necessary for content to be below app bar
  ...theme.mixins.toolbar,
}));

const AppBar = styled(MuiAppBar, {
  shouldForwardProp: (prop) => prop !== 'open',
})(({ theme }) => ({
  zIndex: theme.zIndex.drawer + 1,
  backgroundColor: "rgb(58, 58, 58)",
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

  const [clusterOpen, setClusterOpen] = useState(false);
  const { list: clusterList = [], selectedCluster = "", kubeAuthenticated = false } = useSelector(state => state.cluster)
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
    if (!authenticated || !name || !clusterList?.length || clusterAction) {
      setClusterAction("")
      return
    }
    // Only navigate to cluster page if explicitly switching clusters
    if (switchCluster) {
      navigate("/")
    }
    const cluster = clusterList.find(item => item.name === name)

    dispatch(clusterActions.setSelectedCluster(cluster))
    dispatch(clusterActions.login(cluster))
    setCookie("selectedCluster", name)
    setSwitchCluster("")
  }, [authenticated, clusterList, clusterAction, navigate, dispatch, switchCluster]);

  useEffect(() => {
    !token && handleLogout()
  }, [token, handleLogout])
  useEffect(() => {
    handleConfirmSelectCluster(c_selectedCluster)
  }, [clusterList, authenticated, c_selectedCluster, handleConfirmSelectCluster])

  useEffect(() => {
    if (!authenticated || !user) return
    setUsername(user.username)
    handleGetClusterList()
  }, [authenticated, user, setUsername, handleGetClusterList])

  const handleSelectCluster = (name) => {
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
  }

  const handleCopyRBACCommand = async () => {
    try {
      // Fetch the RBAC command from SnapAPI
      const response = await rbacApi.getRbacCommand();
      
      if (!response.success || !response.command) {
        throw new Error('Failed to get RBAC command from server');
      }

      const rbacCommand = response.command;

      // Check if modern clipboard API is available
      if (navigator.clipboard && navigator.clipboard.writeText) {
        try {
          await navigator.clipboard.writeText(rbacCommand);
          enqueueSnackbar("RBAC setup command copied to clipboard!", { variant: "success" });
          return;
        } catch (clipboardErr) {
          console.warn("Modern clipboard API failed, trying fallback:", clipboardErr);
        }
      }

      // Fallback for older browsers or if clipboard API fails
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
        // Try to focus and select the text
        textArea.focus();
        textArea.select();
        textArea.setSelectionRange(0, 99999); // For mobile devices
        
        // Try the copy command
        const successful = document.execCommand('copy');
        
        if (successful) {
          enqueueSnackbar("RBAC setup command copied to clipboard!", { variant: "success" });
        } else {
          // If execCommand fails, show the command in a modal for manual copy
          enqueueSnackbar("Auto-copy failed. Command will be displayed for manual copy.", { variant: "warning" });
          
          // Create a modal to show the command for manual copying
          const modal = document.createElement("div");
          modal.style.cssText = `
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background: rgba(0,0,0,0.8);
            z-index: 10000;
            display: flex;
            align-items: center;
            justify-content: center;
            padding: 20px;
            box-sizing: border-box;
          `;
          
          const content = document.createElement("div");
          content.style.cssText = `
            background: white;
            padding: 20px;
            border-radius: 8px;
            max-width: 90%;
            max-height: 90%;
            overflow: auto;
            position: relative;
          `;
          
          const closeBtn = document.createElement("button");
          closeBtn.textContent = "Close";
          closeBtn.style.cssText = `
            position: absolute;
            top: 10px;
            right: 10px;
            background: #f44336;
            color: white;
            border: none;
            padding: 5px 10px;
            border-radius: 4px;
            cursor: pointer;
          `;
          closeBtn.onclick = () => {
            document.body.removeChild(modal);
          };
          
          const commandText = document.createElement("textarea");
          commandText.value = rbacCommand;
          commandText.style.cssText = `
            width: 100%;
            height: 300px;
            font-family: monospace;
            font-size: 12px;
            border: 1px solid #ccc;
            padding: 10px;
            margin: 10px 0;
            resize: vertical;
            user-select: all;
            -webkit-user-select: all;
            -moz-user-select: all;
            -ms-user-select: all;
          `;
          
          const instructions = document.createElement("p");
          instructions.textContent = "Please manually copy the command above:";
          instructions.style.cssText = "margin: 10px 0; font-weight: bold;";
          
          const copyButton = document.createElement("button");
          copyButton.textContent = "Copy Command";
          copyButton.style.cssText = `
            background: #4CAF50;
            color: white;
            border: none;
            padding: 10px 20px;
            border-radius: 4px;
            cursor: pointer;
            margin: 10px 5px;
            font-size: 14px;
          `;
          copyButton.onclick = () => {
            commandText.focus();
            commandText.select();
            try {
              const successful = document.execCommand('copy');
              if (successful) {
                enqueueSnackbar("Command copied to clipboard!", { variant: "success" });
              } else {
                enqueueSnackbar("Please manually select and copy the text (Ctrl+C)", { variant: "info" });
              }
            } catch (err) {
              enqueueSnackbar("Please manually select and copy the text (Ctrl+C)", { variant: "info" });
            }
          };
          
          const selectAllButton = document.createElement("button");
          selectAllButton.textContent = "Select All";
          selectAllButton.style.cssText = `
            background: #2196F3;
            color: white;
            border: none;
            padding: 10px 20px;
            border-radius: 4px;
            cursor: pointer;
            margin: 10px 5px;
            font-size: 14px;
          `;
          selectAllButton.onclick = () => {
            commandText.focus();
            commandText.select();
          };
          
          const buttonContainer = document.createElement("div");
          buttonContainer.style.cssText = "text-align: center; margin: 10px 0;";
          buttonContainer.appendChild(selectAllButton);
          buttonContainer.appendChild(copyButton);
          
          content.appendChild(closeBtn);
          content.appendChild(instructions);
          content.appendChild(commandText);
          content.appendChild(buttonContainer);
          modal.appendChild(content);
          document.body.appendChild(modal);
          
          // Focus the textarea for easy selection
          setTimeout(() => {
            commandText.focus();
            commandText.select();
          }, 100);
        }
      } catch (execErr) {
        console.error("execCommand failed:", execErr);
        enqueueSnackbar("Copy failed. Please try again or check browser permissions.", { variant: "error" });
      } finally {
        // Always clean up the textarea
        if (textArea && textArea.parentNode) {
          textArea.parentNode.removeChild(textArea);
        }
      }
      
    } catch (err) {
      console.error("Error copying RBAC command:", err);
      enqueueSnackbar("Failed to copy command. Please try again.", { variant: "error" });
    }
  }

  const renderSwitchCluster = () => {
    return (
      <DialogComponent open={!!switchCluster} onClose={() => setSwitchCluster("")} paperProps={{ maxWidth: 500 }}>
        <Box gap={2} display={"flex"} flexDirection={"column"}>
          <Typography variant='h5'>Cluster management</Typography>
          <Typography variant='h6'>{`Name: ${switchCluster}`}</Typography>
          <Box display={"flex"} width={"100%"} gap={1}>
            <Button variant="contained" style={{ textTransform: "capitalize" }} fullWidth onClick={() => handleConfirmSelectCluster(switchCluster)}>Switch</Button>
            <Button variant="contained" style={{ textTransform: "capitalize" }} fullWidth color="error" onClick={handleRemoveCluster}>Remove</Button>
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
      <DialogComponent open={clusterOpen} onClose={handleClearClusterForm} paperProps={{ maxWidth: 500 }}>
        <Box sx={{ p: 1 }}>
          <Typography variant="h5" sx={{ fontWeight: 'bold', mb: 1 }}>
          Add Cluster
          </Typography>
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

          {renderAuthenticationDetails()}
          <Button variant="outlined" component="label" style={{ width: 200, textTransform: "capitalize" }} startIcon={<CloudUpload />}>
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
          
          <Button 
            variant="outlined" 
            style={{ textTransform: "capitalize", marginBottom: "8px" }} 
            startIcon={<ContentCopy />}
            onClick={handleCopyRBACCommand}
          >
            Copy RBAC Setup Command
          </Button>
          
          <Button variant="contained" style={{ textTransform: "capitalize" }} onClick={handleAddCluster}>Submit</Button>
        </Box>
      </DialogComponent>
    )
  }

  const isSelected = (path) => {
    return window.location.pathname === path
  }

  const renderDrawer = () => {
    if (!authenticated) return
    const mainMenu = [
      { text: "Pods", path: "/pods", Icon: ImageIcon },
      { text: "Checkpoints", path: "/checkpoints", Icon: CheckpointIcon },
      { text: "Registry", path: "/registry", Icon: StorageIcon },
      { text: "Secrets", path: "/secrets", Icon: SecurityIcon },
      { text: "Users", path: "/users", Icon: UsersIcon },
      { text: "SnapWatcher", path: "/snapwatcher", Icon: WatchersIcon },
      { text: "SnapHook", path: "/snaphook", Icon: SnapHookIcon },
    ]

    const showNavigation = kubeAuthenticated && selectedCluster

    return (
      <Drawer variant="permanent" open={open} sx={{ marginTop: "64px" }}>
        <DrawerHeader>
          {/* <IconButton onClick={handleDrawerClose}>
            {theme.direction === 'rtl' ? <ChevronRightIcon /> : <ChevronLeftIcon />}
          </IconButton> */}
        </DrawerHeader>
        <Divider />
        <List>
          <ListItem>
            <FormControl sx={{ m: 1, minWidth: 120 }} size="small" fullWidth variant='outlined'>
              <Select
                value={selectedCluster?.name || "default"}
                onChange={(e) => handleSelectCluster(e.target.value)}
              >
                <MenuItem onClick={() => setClusterOpen(true)} value={selectedCluster?.name || "default"} style={{ fontStyle: "italic" }}>Add Cluster</MenuItem>
                {clusterList.map(item => <MenuItem value={item.name} key={item.name}>{item.name}</MenuItem>)}
              </Select>

            </FormControl>
            <Button color="inherit" onClick={() => navigate("/")} sx={{ backgroundColor: isSelected("/") ? selectedBackgroundColor : "inherit" }}>
              <ClusterIcon sx={{ color: isSelected("/") ? "white" : "inherit", }} />
            </Button>
          </ListItem>
          {/* Always show Registry menu item */}
          <ListItem disablePadding sx={{ display: 'block', backgroundColor: isSelected("/registry") ? selectedBackgroundColor : "white" }}>
            <ListItemButton
              onClick={() => navigate("/registry")}
              sx={[{ minHeight: 48, px: 2.5 }, open ? { justifyContent: 'initial' } : { justifyContent: 'center' }]} >
              <ListItemIcon
                sx={[{ minWidth: 0, justifyContent: 'center' }, open ? { mr: 3 } : { mr: 'auto' }]}>
                <StorageIcon sx={{ color: isSelected("/registry") ? "white" : "inherit" }} />
              </ListItemIcon>
              <ListItemText
                primary="Registry"
                sx={[{ opacity: open ? 1 : 0 }, isSelected("/registry") && { color: "white", fontWeight: "bold" }]} />
            </ListItemButton>
          </ListItem>
          
          {/* Show other menu items only when cluster is connected */}
          {showNavigation && mainMenu.filter(item => item.text !== "Registry").map(({ text, path, Icon }, index) => (
            <ListItem key={text} disablePadding sx={{ display: 'block', backgroundColor: isSelected(path) ? selectedBackgroundColor : "white" }}>
              <ListItemButton
                onClick={() => navigate(path)}
                sx={[{ minHeight: 48, px: 2.5 }, open ? { justifyContent: 'initial' } : { justifyContent: 'center' }]} >
                <ListItemIcon
                  sx={[{ minWidth: 0, justifyContent: 'center' }, open ? { mr: 3 } : { mr: 'auto' }]}>
                  <Icon sx={{ color: isSelected(path) ? "white" : "inherit" }} />
                </ListItemIcon>
                <ListItemText
                  primary={text}
                  sx={[{ opacity: open ? 1 : 0 }, isSelected(path) && { color: "white", fontWeight: "bold" }]} />
              </ListItemButton>
            </ListItem>
          ))}
        </List>
        <Divider />
        <List>
          {authenticated && <ListItem key={"Logout"} disablePadding sx={{ display: 'block' }} onClick={handleLogout}>
            <ListItemButton
              sx={[{ minHeight: 48, px: 2.5, }, open ? { justifyContent: 'initial' } : { justifyContent: 'center' },]} >
              <ListItemIcon sx={[{ minWidth: 0, justifyContent: 'center', }, open ? { mr: 3, } : { mr: 'auto', },]} >
                <MeetingRoomIcon />
              </ListItemIcon>
              <ListItemText
                primary={"Logout"}
                sx={[open ? { opacity: 1 } : { opacity: 0 }
                ]}
              />
            </ListItemButton>
          </ListItem>}
        </List>
      </Drawer>
    )
  }

  return (
    <>

      <Box sx={{ display: 'flex' }}>
        <CssBaseline />
        {renderSwitchCluster()}
        {renderClusterForm()}
        {authenticated && <AppBar position="fixed" open={open} component="nav">
          <Toolbar>
            <Stack direction="row" spacing={2} sx={{ alignItems: "flex-end", justifyContent: "space-between", flexGrow: 1 }}>
              <Typography variant="h6" noWrap component="div">
                Admin Panel
              </Typography>
              <Stack direction="row" spacing={1} alignItems="center">
                <Button
                  color="inherit"
                  onClick={() => setHelpDialogOpen(true)}
                  startIcon={<HelpIcon />}
                  sx={{ textTransform: "capitalize" }}
                >
                  Help
                </Button>
                <Box
                  component="img"
                  sx={{
                    height: 45,
                    filter: 'brightness(0) invert(1)',
                  }}
                  alt="SNAP logo."
                  src="/logo.png"
                />
              </Stack>
            </Stack>
          </Toolbar>
        </AppBar>}
        {renderDrawer()}
        <Box component="main" sx={{ flexGrow: 1, p: 3, backgroundColor: "#f5f5f5", position: "relative", paddingBottom: "80px" }} width={"100%"} height={"100%"} minHeight={"100vh"}>
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
