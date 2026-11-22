import http from 'k6/http';
import { check, sleep } from 'k6';

export const options = {
  scenarios: {
    constante: {
      executor: 'constant-arrival-rate',
      rate: 200,
      timeUnit: '1s',
      duration: '30s',
      preAllocatedVUs: 50,
      maxVUs: 150,
    },
  },
  thresholds: {
    http_req_duration: ['p(95)<300'],
    http_req_failed: ['rate<0.01'],
  },
};

const BASE_URL = __ENV.API_URL || 'http://localhost:8000';

export default function () {
  const res = http.get(`${BASE_URL}/v1/salud`);
  check(res, {
    'status es 200': (r) => r.status === 200,
  });
  sleep(0.1);
}
