import { useEffect, useState } from 'react';
import { styled, useTheme } from '@mui/material/styles';
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
import { Button, FormControl, IconButton, MenuItem, Select, TextField, InputLabel } from '@mui/material';
import DialogComponent from './common/Dialog';
import { useSnackbar } from 'notistack';
import Stack from '@mui/material/Stack';
import { clusterActions } from '../features/cluster/clusterSlice';
import { clusterApi } from '../api/clusterApi';
import { registryActions } from '../features/registry/registrySlice';
import UsersIcon from '@mui/icons-material/Group';
import ClusterIcon from '@mui/icons-material/Tune';
import ProgressTracker from './common/TaskProgressDetails';
import { useProgress } from './common/ProgressContext';
import { CloudUpload } from '@mui/icons-material';

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
  const { setUsername } = useProgress();
  const navigate = useNavigate()
  const dispatch = useDispatch()
  const [open, setOpen] = useState(true);
  const [switchCluster, setSwitchCluster] = useState(false);
  const [clusterName, setClusterName] = useState("");
  const [clusterUrl, setClusterUrl] = useState("");
  const [clusterUsername, setClusterUsername] = useState("");
  const [clusterPassword, setClusterPassword] = useState("");
  const [clusterConfirmPassword, setClusterConfirmPassword] = useState("");
  const [clusterAction, setClusterAction] = useState("");
  const [nodesUsername, setNodesUsername] = useState("");
  const [sshKey, setSshkey] = useState(null);
  const [clusterFormErrors, setClusterFormErrors] = useState({});
  const [authenticationMethod, setAuthenticationMethod] = useState("username_password");
  const [selectedRegistry, setSelectedRegistry] = useState("");
  const [registryRepo, setRegistryRepo] = useState("snap_images");
  const [availableRegistries, setAvailableRegistries] = useState([]);

  const [clusterOpen, setClusterOpen] = useState(false);
  const { list: clusterList = [], selectedCluster = "", checkpointingEnabled = false, kubeAuthenticated = false } = useSelector(state => state.cluster)
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

  useEffect(() => {
    !token && handleLogout()
  }, [token])
  useEffect(() => {
    handleConfirmSelectCluster(c_selectedCluster)
  }, [clusterList, authenticated])

  useEffect(() => {
    if (!authenticated) return
    setUsername(user.username)
    handleGetClusterList()
  }, [authenticated])

  const handleGetClusterList = async () => {
    dispatch(clusterActions.getList())
  }

  const handleConfirmSelectCluster = async (name) => {
    if (!authenticated || !name || !clusterList?.length || clusterAction) {
      setClusterAction("")
      return
    }
    navigate("/")
    const cluster = clusterList.find(item => item.name === name)

    dispatch(clusterActions.setSelectedCluster(cluster))
    dispatch(clusterActions.login(cluster))
    setCookie("selectedCluster", name)
    setSwitchCluster("")
  }

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

  const handleLogout = () => {
    dispatch(authActions.logout())
    dispatch(clusterActions.clearState())
    dispatch(registryActions.clearState())
    navigate("/")
  }

  const handleAddCluster = async () => {
    // Clear previous errors
    setClusterFormErrors({})
    
    // Validation
    const errors = {}
    if (!clusterName.trim()) errors.name = "Cluster name is required"
    if (!clusterUrl.trim()) errors.url = "Cluster API URL is required"
    if (!nodesUsername.trim()) errors.nodesUsername = "Nodes username is required"
    if (!clusterPassword.trim()) {
      errors.password = authenticationMethod === "token" ? "Token is required" : "Password is required"
    }
    
    if (authenticationMethod === "username_password") {
      if (!clusterUsername.trim()) errors.username = "Username is required"
      if (clusterPassword !== clusterConfirmPassword) errors.confirmPassword = "Passwords do not match"
    }
    
    if (Object.keys(errors).length > 0) {
      setClusterFormErrors(errors)
      return
    }

    enqueueSnackbar("Creating new cluster initiated...", { variant: "info" })
    setClusterAction("create")
    
    await clusterApi.create({
      name: clusterName,
      kube_api_url: clusterUrl,
      kube_username: authenticationMethod === "token" ? null : clusterUsername,
      kube_password: clusterPassword,
      nodes_username: nodesUsername,
      auth_method: authenticationMethod,
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
    setClusterUsername("")
    setClusterPassword("")
    setClusterConfirmPassword("")
    setNodesUsername("")
    setSshkey(null)
    setSelectedRegistry("")
    setRegistryRepo("snap_images")
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
    if (authenticationMethod === "token") {
      return (
        <TextField
          label="Token"
          type="password"
          onChange={(e) => setClusterPassword(e.target.value)}
          value={clusterPassword}
          helperText={clusterFormErrors?.password}
          error={!!clusterFormErrors?.password}
        />
      )
    }
    return (
      <>
        <TextField
          label="Cluster Username"
          onChange={(e) => setClusterUsername(e.target.value)}
          value={clusterUsername}
          helperText={clusterFormErrors?.username}
          error={!!clusterFormErrors?.username}
        />
        <TextField
          label="Password"
          type={"password"}
          onChange={(e) => setClusterPassword(e.target.value)}
          value={clusterPassword}
          helperText={clusterFormErrors?.password}
          error={!!clusterFormErrors?.password}
        />
        <TextField
          label="Confirm Password"
          type={"password"}
          onChange={(e) => setClusterConfirmPassword(e.target.value)}
          value={clusterConfirmPassword}
          error={!!clusterFormErrors?.confirmPassword}
          helperText={clusterFormErrors?.confirmPassword}
        />
      </>
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

          <FormControl sx={{ minWidth: 120 }} fullWidth variant='outlined'>
            <InputLabel>Authentication Method</InputLabel>
            <Select
              value={authenticationMethod}
              onChange={(e) => setAuthenticationMethod(e.target.value)}
              label="Authentication Method"
            >
              <MenuItem value={"username_password"} key={"username_password"}>{"Username + Password (default)"}</MenuItem>
              <MenuItem value={"token"} key={"token"}>{"Token"}</MenuItem>
            </Select>
          </FormControl>
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
          <TextField
            label="Nodes Username"
            onChange={(e) => setNodesUsername(e.target.value)}
            value={nodesUsername}
            helperText={clusterFormErrors?.nodesUsername}
            error={!!clusterFormErrors?.nodesUsername}
          />
          
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
              <Stack direction="row" spacing={1} alignItems="flex-end" divider={<Divider variant="inset" orientation="vertical" sx={{ borderColor: "white" }} flexItem />}>
                <Typography variant="h6" sx={{ lineHeight: 1 }} noWrap component="div">SNAP</Typography>
                <Box
                  component="img"
                  sx={{
                    height: 28,
                  }}
                  alt="Your logo."
                  src="/weaver_06.svg"
                />
              </Stack>
            </Stack>
          </Toolbar>
        </AppBar>}
        {renderDrawer()}
        <Box component="main" sx={{ flexGrow: 1, p: 3, backgroundColor: "#f5f5f5", position: "relative" }} width={"100%"} height={"100%"} minHeight={"100vh"}>
          <DrawerHeader />
          {authenticated && <ProgressTracker />}
          {children}
        </Box>
      </Box>
    </>
  );
}
