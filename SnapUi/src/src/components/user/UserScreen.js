import { Box, Button, Card, CircularProgress, FormControl, Grid2 as Grid, InputLabel, MenuItem, Paper, Select, TextField, Typography, Tabs, Tab, Checkbox, Autocomplete, Chip, Divider, FormControlLabel } from "@mui/material"
import { useEffect, useState } from "react";
import TableComponent from "../common/Table";
import { useSnackbar } from 'notistack';
import Stack from '@mui/material/Stack';
import IconButton from '@mui/material/IconButton';
import Tooltip from '@mui/material/Tooltip';
import { useDispatch, useSelector } from "react-redux";
import DialogComponent from "../common/Dialog";
import { registryActions } from "../../features/registry/registrySlice";
import { registryApi } from "../../api/registryApi";
import DeleteIcon from '@mui/icons-material/Delete';
import { usersActions } from "../../features/users/usersSlice";
import { userApi } from "../../api/userApi";
import { Loading } from "../common/loading";
import EditIcon from '@mui/icons-material/Edit';
import AddIcon from '@mui/icons-material/Add';
import { CustomerContainer } from "../common/CustomContainer";
import SecurityIcon from '@mui/icons-material/Security';
const UserScreen = ({ classes }) => {
  const dispatch = useDispatch()
  const { enqueueSnackbar } = useSnackbar();
  const { list: userList = [], loading: userListLoading } = useSelector(state => state.users)
  const [loading, setLoading] = useState(false)
  const [dialogType, setDialogType] = useState("")
  const [data, setData] = useState([])
  const [total, setTotal] = useState(0)
  const [rowsPerPage, setRowsPerPage] = useState(5)
  const [page, setPage] = useState(0)
  const [error, setError] = useState('')
  const [currentRowItem, setCurrentRowItem] = useState(null)
  const [isEdit, setIsEdit] = useState(false)
  const [registry, setRegistry] = useState("")
  const [name, setName] = useState("")
  const [username, setUsername] = useState("")
  const [password, setPassword] = useState("")
  const [role, setRole] = useState("")
  const [isActionLoading, setIsActionLoading] = useState(false)
  const [searchTerm, setSearchTerm] = useState("")
  
  // AD Configuration state
  const [tabValue, setTabValue] = useState(0)
  const [adEnabled, setAdEnabled] = useState(false)
  const [adType, setAdType] = useState("openldap")
  const [adServer, setAdServer] = useState("")
  const [adPort, setAdPort] = useState(389)
  const [adBaseDn, setAdBaseDn] = useState("")
  const [adServiceDn, setAdServiceDn] = useState("")
  const [adServicePassword, setAdServicePassword] = useState("")
  const [adAllowedGroups, setAdAllowedGroups] = useState([])
  const [adUseSsl, setAdUseSsl] = useState(false)
  const [adAvailableGroups, setAdAvailableGroups] = useState([])
  const [adConfigLoading, setAdConfigLoading] = useState(false)
  const [adTestLoading, setAdTestLoading] = useState(false)
  const [adTestResult, setAdTestResult] = useState(null)

  useEffect(() => {
    handleGetUserList();
    loadADConfig();
  }, [])

  const handleGetUserList = () => {
    dispatch(usersActions.getList())
  }


  const handleRowsPerPageChange = (event) => {
    setRowsPerPage(+event.target.value);
    setPage(0);
  };

  const handlePageChange = (event, newPage) => {
    setPage(newPage);
  };

  const handleDeleteUser = async () => {
    try {
      setIsActionLoading(true)
      await userApi.remove(currentRowItem.name)
      handleGetUserList()
      enqueueSnackbar(`User ${currentRowItem.name} successfully deleted`, { variant: "success" })
    } catch (error) {
      console.error("User delete error", error.toString())
      enqueueSnackbar(`User ${currentRowItem.name} deletion failed`, { variant: "error" })
    }
    handleClearDialog()
  }



  const handleSubmit = async () => {

    if (isEdit) {
      setIsActionLoading(true)
      enqueueSnackbar(`User ${name} update initiated`, { variant: "info" })
      try {
        await userApi.update({
          name: name,
          username: username,
          password: password,
          role: role
        })
        enqueueSnackbar(`User ${name} successfully updated`, { variant: "success" })
      } catch (error) {
        console.error("User update error", error.toString())
        enqueueSnackbar(`User ${name} update failed`, { variant: "error" })
      }
    } else {
      enqueueSnackbar(`User ${name} creation initiated`, { variant: "info" })
      try {
        await userApi.create({
          name: name,
          username: username,
          password: password,
          role: role
        })
        enqueueSnackbar(`User ${name} successfully created`, { variant: "success" })
      } catch (error) {
        console.error("User creation error", error.toString())
        enqueueSnackbar(`User ${name} creation failed`, { variant: "error" })
      }
    }
    handleGetUserList()
    handleClearDialog()
  }

  //diaglog for analysis logs
  const handleOpenEditDialog = (user) => {
    setDialogType("userForm")
    setCurrentRowItem(user)
    setName(user.userdetails.name)
    setUsername(user.name)
    setPassword(user.userdetails.password)
    setRole(user.userdetails.role)
    setIsEdit(true)
  }

  const handleOpenDeleteDialog = (user) => {
    setDialogType("userDelete")
    setCurrentRowItem(user)
  }

  const handleClearDialog = () => {
    setIsActionLoading(false)
    setLoading(false)
    setDialogType("")
    setRegistry("")
    setName("")
    setUsername("")
    setPassword("")
    setIsEdit(false)
    setCurrentRowItem(null)
  }

  const renderUserDeleteDialog = () => {
    return (
      <DialogComponent open={!!dialogType} onClose={() => handleClearDialog("")} paperProps={{ maxWidth: 500 }}>
        <Box gap={2} display={"flex"} flexDirection={"column"}>
          <Typography variant="h5">Delete User</Typography>
          <Typography>Are you sure you want to delete {currentRowItem?.name} user?</Typography>
          <Button variant="contained" onClick={() => handleDeleteUser()}>Delete</Button>
        </Box>
      </DialogComponent>
    )
  }

  const renderUserForm = () => {
    return (
      <DialogComponent open={!!dialogType} onClose={() => handleClearDialog("")} paperProps={{ maxWidth: 500 }}>
        <Box gap={2} display={"flex"} flexDirection={"column"}>
          <Typography variant="h5">{isEdit ? "Edit User" : "Add New User"}</Typography>
          <TextField
            label="Username"
            onChange={(e) => setUsername(e.target.value)}
            value={username}
            disabled={isEdit}
          />
          <FormControl fullWidth>
            <InputLabel id="role-select-label">Role</InputLabel>
            <Select
              labelId="role-select-label"
              id="role-select"
              value={role}
              label="Role"
              onChange={(e) => setRole(e.target.value)}
            >
              <MenuItem value="admin">Admin</MenuItem>
              <MenuItem value="user">User</MenuItem>
            </Select>
          </FormControl>
          <TextField
            label="Name"
            onChange={(e) => setName(e.target.value)}
            value={name}
          />
          <TextField
            type='password'
            label="Password"
            onChange={(e) => setPassword(e.target.value)}
            value={password}
          />
          <Button variant="contained" onClick={handleSubmit}>{isEdit ? "Update" : "Add"}</Button>
        </Box>
      </DialogComponent>
    )
  }

  const renderDialog = () => {
    const dialogContent = {
      userForm: renderUserForm(),
      userDelete: renderUserDeleteDialog(),
    }
    return dialogContent[dialogType]
  }

  const tableHeaders = [
    { name: "Username", key: "name" },
    { name: "Name", key: "userdetails.name" },
    { name: "Role", key: "userdetails.role" },
    {
      name: "Actions", key: "", action: (data) => (
        <>
          {
            <Stack direction="row" spacing={1}>
              {currentRowItem && currentRowItem?.name === data?.name && isActionLoading ? <CircularProgress />
                :
                <>
                  <Tooltip title={"Edit User"} placement="top">
                    <IconButton aria-label="edit user" size="small" onClick={() => handleOpenEditDialog(data)}>
                      <EditIcon color="primary" fontSize="small" />
                    </IconButton>
                  </Tooltip>
                  <Tooltip title="Delete User" placement="top">
                    <IconButton aria-label="delete user" size="small" onClick={() => handleOpenDeleteDialog(data)}>
                      <DeleteIcon color="error" fontSize="small" />
                    </IconButton>
                  </Tooltip>
                </>
              }

            </Stack>
          }
        </>
      )
    },
  ]

  const renderError = () => {
    return (
      <Grid size={4}>
        <Typography color="error">{error}</Typography>
      </Grid>
    )
  }

  // AD Configuration handlers
  const loadADConfig = async () => {
    setAdConfigLoading(true);
    try {
      const response = await userApi.getADConfig();
      // Handle axios response structure - data is in response.data
      const result = response?.data || response;
      if (result?.success) {
        const config = result.ad_config || {};
        setAdEnabled(config.ad_enabled || false);
        setAdType(config.ad_type || "openldap");
        setAdServer(config.ad_server || "");
        setAdPort(config.ad_port || 389);
        setAdBaseDn(config.ad_base_dn || "");
        setAdServiceDn(config.ad_service_dn || "");
        setAdServicePassword(config.ad_service_password || "");
        setAdAllowedGroups(config.ad_allowed_groups || []);
        setAdUseSsl(config.ad_use_ssl || false);
      } else {
        // If AD config doesn't exist, reset to defaults
        setAdEnabled(false);
        setAdType("openldap");
        setAdServer("");
        setAdPort(389);
        setAdBaseDn("");
        setAdServiceDn("");
        setAdServicePassword("");
        setAdAllowedGroups([]);
        setAdUseSsl(false);
      }
    } catch (error) {
      console.error("Failed to load AD config:", error);
    } finally {
      setAdConfigLoading(false);
    }
  }

  const loadADGroups = async () => {
    if (!adEnabled) return;
    
    try {
      const response = await userApi.getADGroups();
      // Handle axios response structure - data is in response.data
      const result = response?.data || response;
      if (result?.success) {
        setAdAvailableGroups(result.groups || []);
      }
    } catch (error) {
      console.error("Failed to load AD groups:", error);
      enqueueSnackbar("Failed to load AD groups", { variant: "error" });
    }
  }

  const handleTestADConnection = async () => {
    if (!adServer || !adBaseDn || !adServiceDn || !adServicePassword) {
      enqueueSnackbar("Please fill in all required AD connection fields", { variant: "warning" });
      return;
    }

    setAdTestLoading(true);
    setAdTestResult(null);
    try {
      const testConfig = {
        ad_type: adType,
        ad_server: adServer,
        ad_port: adPort,
        ad_base_dn: adBaseDn,
        ad_service_dn: adServiceDn,
        ad_service_password: adServicePassword,
        ad_use_ssl: adUseSsl
      };
      const response = await userApi.testADConnection(testConfig);
      // Handle axios response structure - data is in response.data
      const result = response?.data || response;
      setAdTestResult(result);
      if (result?.success) {
        enqueueSnackbar("AD connection test successful", { variant: "success" });
        if (adEnabled) {
          await loadADGroups();
        }
      } else {
        const errorMsg = result?.message || result?.detail || "Connection test failed";
        enqueueSnackbar(`Connection test failed: ${errorMsg}`, { variant: "error" });
      }
    } catch (error) {
      console.error("Failed to test AD connection:", error);
      const errorMsg = error?.response?.data?.message || error?.response?.data?.detail || error?.message || "Unknown error";
      setAdTestResult({ success: false, message: errorMsg });
      enqueueSnackbar(`Failed to test AD connection: ${errorMsg}`, { variant: "error" });
    } finally {
      setAdTestLoading(false);
    }
  }

  const handleSaveADConfig = async () => {
    if (adEnabled && (!adServer || !adBaseDn || !adServiceDn || !adServicePassword)) {
      enqueueSnackbar("Please fill in all required AD connection fields", { variant: "warning" });
      return;
    }

    setAdConfigLoading(true);
    try {
      const adConfig = {
        ad_enabled: adEnabled,
        ad_type: adType,
        ad_server: adServer,
        ad_port: adPort,
        ad_base_dn: adBaseDn,
        ad_service_dn: adServiceDn,
        ad_service_password: adServicePassword,
        ad_allowed_groups: adAllowedGroups,
        ad_use_ssl: adUseSsl
      };
      const response = await userApi.updateADConfig(adConfig);
      // Handle axios response structure - data is in response.data
      const result = response?.data || response;
      if (result?.success) {
        enqueueSnackbar("AD configuration saved successfully", { variant: "success" });
        await loadADConfig();
      } else {
        const errorMsg = result?.message || result?.detail || "Failed to save AD configuration";
        enqueueSnackbar(`Failed to save AD configuration: ${errorMsg}`, { variant: "error" });
      }
    } catch (error) {
      console.error("Failed to save AD config:", error);
      const errorMsg = error?.response?.data?.message || error?.response?.data?.detail || error?.message || "Unknown error";
      enqueueSnackbar(`Failed to save AD configuration: ${errorMsg}`, { variant: "error" });
    } finally {
      setAdConfigLoading(false);
    }
  }

  useEffect(() => {
    if (adEnabled) {
      loadADGroups();
    }
  }, [adEnabled])

  const filteredData = userList.filter(item => {
    const searchFields = [
      item.name,
      item.userdetails.name
    ];
    return searchFields.some(field => String(field).toLowerCase().includes(searchTerm.toLowerCase()))
  })

  return (
    <CustomerContainer title="Users">
      <Tabs value={tabValue} onChange={(e, newValue) => setTabValue(newValue)} sx={{ mb: 3 }}>
        <Tab label="Local Users" />
        <Tab label="Active Directory Integration" />
      </Tabs>

      {tabValue === 0 && (
        <>
          {userListLoading ? <Loading /> : (
            <>
              <Button
                variant="contained"
                onClick={() => setDialogType("userForm")}
                sx={{
                  backgroundColor: 'primary.main',
                  borderRadius: '8px',
                  textTransform: 'none',
                  mb: 2,
                  px: 3,
                  py: 1,
                  '&:hover': {
                    backgroundColor: 'primary.dark',
                    boxShadow: 2,
                  },
                }}
                startIcon={<AddIcon />}
              >
                Add User
              </Button>
              <Paper elevation={0} sx={{ px: 3, py: 1, bgcolor: 'background.paper', borderRadius: 2 }}>
                {renderError()}
                {renderDialog()}
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, marginBlock: 2, ml: 1 }}>
                  <Typography variant="h6" gutterBottom component="div">
                    Search
                  </Typography>
                  <TextField
                    sx={{ width: '300px' }}
                    size="small"
                    placeholder="Username, Name"
                    value={searchTerm}
                    onChange={(e) => setSearchTerm(e.target.value)}
                  />
                </Box>
                <TableComponent
                  classes={classes}
                  data={filteredData}
                  tableHeaders={tableHeaders}
                  total={filteredData.length}
                  rowsPerPage={rowsPerPage}
                  page={page}
                  handleRowsPerPageChange={handleRowsPerPageChange}
                  handlePageChange={handlePageChange}
                />
              </Paper>
            </>
          )}
        </>
      )}

      {tabValue === 1 && (
        <Paper elevation={0} sx={{ p: 3, bgcolor: 'background.paper', borderRadius: 2 }}>
          <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 3 }}>
            <Typography variant="h6" sx={{ fontWeight: 'bold' }}>
              Active Directory Integration
            </Typography>
            <FormControlLabel
              control={
                <Checkbox
                  checked={adEnabled}
                  onChange={(e) => setAdEnabled(e.target.checked)}
                  disabled={adConfigLoading}
                />
              }
              label="Enable AD Integration"
            />
          </Box>

          {adEnabled && (
            <Box>
              <Stack spacing={3}>
                <FormControl fullWidth>
                  <InputLabel>AD Type</InputLabel>
                  <Select
                    value={adType}
                    onChange={(e) => setAdType(e.target.value)}
                    label="AD Type"
                    disabled={adConfigLoading}
                  >
                    <MenuItem value="openldap">OpenLDAP</MenuItem>
                    <MenuItem value="real_ad">Real Active Directory</MenuItem>
                  </Select>
                </FormControl>

                <TextField
                  fullWidth
                  label="AD Server"
                  value={adServer}
                  onChange={(e) => setAdServer(e.target.value)}
                  placeholder="e.g., 192.168.33.209 or ad.company.com"
                  disabled={adConfigLoading}
                  required
                />

                <TextField
                  fullWidth
                  label="Port"
                  type="number"
                  value={adPort}
                  onChange={(e) => setAdPort(parseInt(e.target.value) || 389)}
                  disabled={adConfigLoading}
                  helperText={adUseSsl ? "LDAPS typically uses port 636" : "LDAP typically uses port 389"}
                />

                <FormControlLabel
                  control={
                    <Checkbox
                      checked={adUseSsl}
                      onChange={(e) => {
                        setAdUseSsl(e.target.checked);
                        if (e.target.checked && adPort === 389) {
                          setAdPort(636);
                        } else if (!e.target.checked && adPort === 636) {
                          setAdPort(389);
                        }
                      }}
                      disabled={adConfigLoading}
                    />
                  }
                  label="Use SSL (LDAPS)"
                />

                <TextField
                  fullWidth
                  label="Base DN"
                  value={adBaseDn}
                  onChange={(e) => setAdBaseDn(e.target.value)}
                  placeholder="e.g., dc=mycompany,dc=local"
                  disabled={adConfigLoading}
                  required
                />

                <TextField
                  fullWidth
                  label="Service Account DN"
                  value={adServiceDn}
                  onChange={(e) => setAdServiceDn(e.target.value)}
                  placeholder="e.g., cn=admin,dc=mycompany,dc=local"
                  disabled={adConfigLoading}
                  required
                />

                <TextField
                  fullWidth
                  label="Service Account Password"
                  type="password"
                  value={adServicePassword}
                  onChange={(e) => setAdServicePassword(e.target.value)}
                  disabled={adConfigLoading}
                  required
                />

                <Box sx={{ display: 'flex', gap: 2, alignItems: 'center' }}>
                  <Button
                    variant="outlined"
                    onClick={handleTestADConnection}
                    disabled={adTestLoading || adConfigLoading || !adServer || !adBaseDn || !adServiceDn || !adServicePassword}
                    startIcon={adTestLoading ? <CircularProgress size={20} /> : <SecurityIcon />}
                  >
                    {adTestLoading ? "Testing..." : "Test Connection"}
                  </Button>
                  {adTestResult && (
                    <Chip
                      label={adTestResult.success ? "Connection Successful" : `Failed: ${adTestResult.message}`}
                      color={adTestResult.success ? "success" : "error"}
                      size="small"
                    />
                  )}
                </Box>

                <Divider sx={{ my: 2 }} />

                <Typography variant="subtitle2" sx={{ mb: 1 }}>
                  Allowed AD Groups
                </Typography>
                <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
                  Select which AD groups are allowed to access the application. Users must be members of at least one allowed group.
                </Typography>

                <Autocomplete
                  multiple
                  options={adAvailableGroups.map(g => g.name)}
                  value={adAllowedGroups}
                  onChange={(event, newValue) => {
                    setAdAllowedGroups(newValue);
                  }}
                  disabled={adConfigLoading || !adEnabled}
                  renderInput={(params) => (
                    <TextField
                      {...params}
                      label="Allowed AD Groups"
                      placeholder="Select groups..."
                    />
                  )}
                  renderTags={(value, getTagProps) =>
                    value.map((option, index) => (
                      <Chip
                        label={option}
                        {...getTagProps({ index })}
                        key={option}
                      />
                    ))
                  }
                />

                {adAllowedGroups.length > 0 && (
                  <Box>
                    <Typography variant="subtitle2" sx={{ mb: 1 }}>
                      Selected Groups ({adAllowedGroups.length}):
                    </Typography>
                    <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1 }}>
                      {adAllowedGroups.map((group) => (
                        <Chip
                          key={group}
                          label={group}
                          onDelete={() => {
                            setAdAllowedGroups(adAllowedGroups.filter(g => g !== group));
                          }}
                          color="primary"
                          variant="outlined"
                        />
                      ))}
                    </Box>
                  </Box>
                )}

                <Button
                  variant="outlined"
                  onClick={loadADGroups}
                  disabled={adConfigLoading || !adEnabled || !adServer}
                  startIcon={<SecurityIcon />}
                >
                  Refresh Groups List
                </Button>

                <Divider sx={{ my: 3 }} />

                <Box sx={{ display: 'flex', justifyContent: 'flex-end', gap: 2 }}>
                  <Button
                    variant="outlined"
                    onClick={() => loadADConfig()}
                    disabled={adConfigLoading}
                  >
                    Cancel
                  </Button>
                  <Button
                    variant="contained"
                    onClick={handleSaveADConfig}
                    disabled={adConfigLoading}
                    startIcon={adConfigLoading ? <CircularProgress size={20} /> : null}
                  >
                    {adConfigLoading ? "Saving..." : "Save Configuration"}
                  </Button>
                </Box>
              </Stack>
            </Box>
          )}

          {!adEnabled && (
            <Typography variant="body2" color="text.secondary">
              Enable Active Directory integration to allow users to authenticate using their AD credentials.
              Local users will still be able to log in.
            </Typography>
          )}
        </Paper>
      )}
    </CustomerContainer>
  )
}

export default UserScreen;