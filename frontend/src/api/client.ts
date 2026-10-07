import axios from 'axios';

const client = axios.create({
  baseURL: '/api',
  timeout: 120000,
  withCredentials: true,
});

export default client;
