// Auth API layer — session only. The sign-in/sign-up screens live in
// auth_pages.js; this module just talks to /api/auth and maintains the
// cached token + user.

import { api, setToken, setUser, clearToken, clearUser } from './utils.js?v=64';

export function login(email, password) {
  return api('/auth/login', {
    method: 'POST',
    body: JSON.stringify({ email, password }),
  }).then((data) => {
    if (data && data.session && data.session.access_token) setToken(data.session.access_token);
    if (data && data.user) setUser(data.user);
    return data;
  });
}

/**
 * Minimal registration: name, email, password and the role being applied for.
 * Everything else (department, qualifications, competency…) is completed later
 * on the profile screen.
 *
 * `invite` is the token from the link an Administrator shared — only the
 * SUPREME sign-up screen ever sends one, and the server ignores it for the
 * other two roles.
 */
export function register({ name, email, password, role, invite }) {
  const payload = { name, email, password };
  if (role) payload.role = role;
  if (invite) payload.invite = invite;
  return api('/auth/register', {
    method: 'POST',
    body: JSON.stringify(payload),
  }).then((d) => {
    if (d && d.session && d.session.access_token) setToken(d.session.access_token);
    if (d && d.user) setUser(d.user);
    return d;
  });
}

/** True when the account still needs an Administrator to say yes. */
export function isPending(user) {
  return !!user && user.status === 'PENDING';
}

/** Where a freshly signed-in account belongs, given its approval state. */
export function homeFor(user) {
  return isPending(user) ? '/pending' : '/home';
}

export function logout() {
  clearToken();
  clearUser();
}

export function me() {
  return api('/auth/me').then((d) => {
    if (d && d.user) setUser(d.user);
    return d && d.user;
  });
}

/** Exchange a confirmation code from the email link for a live session. */
export function confirm(params) {
  const q = new URLSearchParams();
  if (params.code) q.set('code', params.code);
  if (params.access_token) q.set('access_token', params.access_token);
  return api('/auth/confirm?' + q.toString()).then((d) => {
    if (d && d.session && d.session.access_token) setToken(d.session.access_token);
    if (d && d.user) setUser(d.user);
    return d;
  });
}

export function changePassword(current_password, new_password) {
  return api('/auth/change-password', {
    method: 'POST',
    body: JSON.stringify({ current_password, new_password }),
  });
}
