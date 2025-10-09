import { api } from "../utils/api"

const getRbacCommand = async () => new Promise(async (resolve, reject) => {
    try {
        const response = await api.get(`/rbac/rbac-command`)
        if (!response.data) return reject()
        resolve(response.data)
    } catch (err) {
        reject(err)
    }
})

const refreshRbacCommand = async () => new Promise(async (resolve, reject) => {
    try {
        const response = await api.post(`/rbac/rbac-command/refresh`)
        if (!response.data) return reject()
        resolve(response.data)
    } catch (err) {
        reject(err)
    }
})

export const rbacApi = {
    getRbacCommand,
    refreshRbacCommand
}
