import { api } from "../utils/api"

const getClusterStatus = async (clusterName = null) => new Promise(async (resolve, reject) => {
    try {
        const url = clusterName ? `/cluster/status/summary?cluster_name=${clusterName}` : `/cluster/status/summary`
        const response = await api.get(url)
        if (!response.data) return reject()
        resolve(response.data)
    } catch (err) {
        reject(err)
    }
})

const reportNodeStatus = async (nodeStatusData) => new Promise(async (resolve, reject) => {
    try {
        const response = await api.post(`/cluster/status/report`, nodeStatusData)
        if (!response.data) return reject()
        resolve(response.data)
    } catch (err) {
        reject(err)
    }
})

export const clusterStatusApi = {
    getClusterStatus,
    reportNodeStatus
}
