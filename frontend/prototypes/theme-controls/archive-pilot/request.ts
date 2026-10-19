import axios from 'axios'

// The pilot has no authentication or network interceptor; fixtures own every request.
const request=axios.create({baseURL:'/api'})
request.interceptors.response.use(response=>response.data)
export default request
