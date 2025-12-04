import { AccountCircle, Key } from "@mui/icons-material";
import { Button, Grid2 as Grid, InputAdornment, TextField, Typography, CircularProgress, Stack, Box, ToggleButtonGroup, ToggleButton } from "@mui/material"
import { useEffect, useState } from "react";
import { useNavigate } from 'react-router-dom';
import { useDispatch, useSelector } from "react-redux";
import { authActions, authSlice } from "../features/auth/authSlice";
import { getCookie } from "../utils/cookies";

const Login = () => {
  const dispatch = useDispatch()
  const navigate = useNavigate();
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [authMethod, setAuthMethod] = useState('local') // 'ad' or 'local'
  const [error, setError] = useState('')
  const { authenticated = false, error: authError, loading = false, user } = useSelector(state => state.auth)
  const token = getCookie("token")

  const handleLogin = (e) => {
    e.preventDefault()
    dispatch(authActions.userLogin({
      username,
      password,
      auth_method: authMethod
    }))
  }

  const handleAuthMethodChange = (event, newMethod) => {
    if (newMethod !== null) {
      setAuthMethod(newMethod)
    }
  }

  useEffect(() => {
    if (token && !authenticated) {
      dispatch(authActions.verifyUser())
    }
  }, [token])

  useEffect(() => {
    if (authenticated) return navigate("/")
  }, [authenticated])

  const renderError = () => {
    return (
      <Grid size={4}>
        <Typography color="error">{error || (authError && "Invalid username or password")}</Typography>
      </Grid>
    )
  }

  return (
    <Box
      sx={{
        maxWidth: '400px',
        width: '100%',
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        margin: '0 auto',
        backgroundColor: 'background.paper',
        borderRadius: 2,
        boxShadow: '0 8px 24px rgba(0,0,0,0.08)',
        position: 'relative',
        overflow: 'hidden'
      }}
    >
      <Box
        sx={{
          position: 'absolute',
          top: 0,
          left: 0,
          width: '100%',
          height: '60px',
          background: 'linear-gradient(45deg, #2196F3 30%, #21CBF3 90%)',
          '&::after': {
            content: '""',
            position: 'absolute',
            bottom: 0,
            left: 0,
            width: '100%',
            height: '65px',
            background: 'inherit',
            transform: 'scale(2)',
            borderRadius: '50%'
          }
        }}
      />
      <Stack 
        direction="row" 
        spacing={2} 
        alignItems="center" 
        sx={{ 
          padding: 4,
          width: "100%",
          position: 'relative',
          zIndex: 1
        }} 
        justifyContent="center"
      >
        <Typography
          variant="h6"
          sx={{
            color: "white",
            marginBottom: "-15px!important",
          }}
        >
          SNAP
        </Typography>

        <Box
          component="img"
          sx={{
            height: 40,
            borderLeft: "1px solid white",
            paddingLeft: 1,
          }}
          alt="SNAP logo"
          src="/weaver_06.svg"
        />

      </Stack>
      <Box sx={{
        padding: 4,
        width: "100%",
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        gap: 2,
        position: 'relative',
        zIndex: 1
      }}>
        <Typography
          variant="h4"
          sx={{
            fontWeight: 500,
            background: 'linear-gradient(45deg, #2196F3 30%, #21CBF3 90%)',
            backgroundClip: 'text',
            textFillColor: 'transparent'
          }}
        >
          Sign In
        </Typography>


        {renderError()}

        <form onSubmit={handleLogin} style={{ width: "100%" }}>
          <Stack spacing={3}>
            {/* Authentication Method Selector */}
            <ToggleButtonGroup
              value={authMethod}
              exclusive
              onChange={handleAuthMethodChange}
              fullWidth
              size="small"
              sx={{ mb: -1 }}
            >
              <ToggleButton value="ad" aria-label="active directory" sx={{ py: 0.75 }}>
                <Typography variant="body2" sx={{ fontSize: '0.875rem' }}>AD</Typography>
              </ToggleButton>
              <ToggleButton value="local" aria-label="local" sx={{ py: 0.75 }}>
                <Typography variant="body2" sx={{ fontSize: '0.875rem' }}>Local</Typography>
              </ToggleButton>
            </ToggleButtonGroup>

            <TextField
              label="Username"
              fullWidth
              InputProps={{
                startAdornment: (
                  <InputAdornment position="start">
                    <AccountCircle sx={{ color: 'text.secondary' }} />
                  </InputAdornment>
                ),
              }}
              onChange={(e) => setUsername(e.target.value)}
              value={username}
              variant="outlined"
            />

            <TextField
              fullWidth
              label="Password"
              type="password"
              InputProps={{
                startAdornment: (
                  <InputAdornment position="start">
                    <Key sx={{ color: 'text.secondary' }} />
                  </InputAdornment>
                ),
              }}
              onChange={(e) => setPassword(e.target.value)}
              value={password}
              variant="outlined"
            />

            <Button
              variant="contained"
              type="submit"
              size="large"
              disabled={loading}
              sx={{
                height: 48,
                background: 'linear-gradient(45deg, #2196F3 30%, #21CBF3 90%)',
                boxShadow: '0 3px 5px 2px rgba(33, 203, 243, .3)',
              }}
            >
              {loading ? <CircularProgress size={24} style={{ color: "white" }} /> : 'Sign In'}
            </Button>
          </Stack>
        </form>
      </Box>
    </Box>
  )
}

export default Login;