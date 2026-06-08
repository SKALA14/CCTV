import axios from 'axios'

const api = axios.create({
    baseURL: '/api',
    timeout: 10000,
    withCredentials: true,   // httpOnly 쿠키 자동 전송
})

// 401 응답 시 로그인 페이지로 리다이렉트
api.interceptors.response.use(
    (response) => response,
    (error) => {
        if (error.response?.status === 401) {
            // 로그인 페이지에서의 401은 무시 (로그인 실패 처리는 컴포넌트에서)
            if (!window.location.pathname.includes('/login')) {
                window.location.href = '/login'
            }
        }
        return Promise.reject(error)
    }
)

export default api
