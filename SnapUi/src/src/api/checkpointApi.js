import { api } from "../utils/api"

const getById = async (checkpoint_id) => new Promise(async (resolve, reject) => {
    try {
        const response = await api.get(`/checkpoints/${checkpoint_id}`)
        if( !response.data ) return reject()
        resolve(response.data)
    } catch (err) {
        reject(err)
    }
})

const getList = async () => new Promise(async (resolve, reject) => {
    try {
        const response = await api.get(`/checkpoint/list`)
        if( !response.data ) return reject()
        resolve(response.data)
    } catch (err) {
        reject(err)
    }
})


const createCheckpointKubelet = async (data) => new Promise(async (resolve, reject) => {
    try {
        const response = await api.post(`/checkpoint/kubelet/checkpoint`, data)
        if( !response.data ) return reject()
        resolve(response.data)
    } catch (err) {
        reject(err)
    }
})

const runCheckpointctl = async (pod_name, checkpoint_name) => new Promise(async (resolve, reject) => {
    try {
        const response = await api.post(`/checkpoint/checkpointctl`, { pod_name, checkpoint_name })
        if( !response ) return reject()
        resolve(response.status)
    } catch (err) {
        reject(err)
    }
})

const getCheckpointctlLogs = async (pod_name, checkpoint_name) => new Promise(async (resolve, reject) => {
    try {
        const response = await api.get(`/checkpoint/checkpointctl/information?pod_name=${pod_name}&checkpoint_name=${checkpoint_name}`)
        if( !response.data ) return reject()
        resolve(response.data)
    } catch (err) {
        reject(err)
    }
})

const pushCheckpoint = async (data) => new Promise(async (resolve, reject) => {
    try {
        if (!data?.username) return reject("Username is missing")
        const response = await api.post(`/registry/create_and_push_checkpoint_container`, data)
        if( !response.data ) return reject()
        resolve(response.data)
    } catch (err) {
        reject(err)
    }
})

const scanCheckpoint = async (data) => new Promise(async (resolve, reject) => {
    try {
        const response = await api.post(`/checkpoint/analyze/volatility`, data)
        if( !response.data ) return reject()
        resolve(response.data)
    } catch (err) {
        reject(err)
    }
})

const getScanResults = async (data) => new Promise(async (resolve, reject) => {
    try {
        const response = await api.get(`/checkpoint/analyze/volatility/results?pod_name=${data.pod_name}&checkpoint_name=${data.checkpoint_name}`)
        if( !response.data ) return reject()
        resolve(response.data)
    } catch (err) {
        reject(err)
    }
})

const downloadCheckpoint = async (pod_name, filename) => new Promise(async (resolve, reject) => {
    try {
        const response = await api.get(`/checkpoint/download/${pod_name}?filename=${encodeURIComponent(filename)}`, {
            responseType: 'blob'
        })
        if( !response.data ) return reject()
        
        // Create blob URL and trigger download
        const url = window.URL.createObjectURL(new Blob([response.data]))
        const link = document.createElement('a')
        link.href = url
        link.setAttribute('download', filename)
        document.body.appendChild(link)
        link.click()
        link.remove()
        window.URL.revokeObjectURL(url)
        
        resolve(response.data)
    } catch (err) {
        reject(err)
    }
})

const deleteCheckpoint = async (pod_name, filename) => new Promise(async (resolve, reject) => {
    try {
        const response = await api.delete(`/checkpoint/delete/${pod_name}?filename=${encodeURIComponent(filename)}`)
        if( !response.data ) return reject()
        resolve(response.data)
    } catch (err) {
        reject(err)
    }
})

const fingerprintCheckpoint = async (data) => new Promise(async (resolve, reject) => {
    try {
        const response = await api.post(`/checkpoint/fingerprint`, data)
        if( !response.data ) return reject()
        resolve(response.data)
    } catch (err) {
        reject(err)
    }
})

const compareCheckpointFingerprints = async (data) => new Promise(async (resolve, reject) => {
    try {
        const response = await api.post(`/checkpoint/fingerprint/compare`, data)
        if( !response.data ) return reject()
        resolve(response.data)
    } catch (err) {
        reject(err)
    }
})

const getComponentDiff = async (pod_name_1, checkpoint_name_1, pod_name_2, checkpoint_name_2, component_name) => new Promise(async (resolve, reject) => {
    try {
        const params = new URLSearchParams({
            pod_name_1,
            checkpoint_name_1,
            pod_name_2,
            checkpoint_name_2,
            component_name
        })
        const response = await api.get(`/checkpoint/fingerprint/compare/diff?${params.toString()}`)
        if( !response.data ) return reject()
        resolve(response.data)
    } catch (err) {
        reject(err)
    }
})

export const checkpointApi = {
    getById,
    getList,
    createCheckpointKubelet,
    runCheckpointctl,
    getCheckpointctlLogs,
    pushCheckpoint,
    scanCheckpoint,
    getScanResults,
    downloadCheckpoint,
    deleteCheckpoint,
    fingerprintCheckpoint,
    compareCheckpointFingerprints,
    getComponentDiff

}