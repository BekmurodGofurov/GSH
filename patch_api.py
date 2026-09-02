with open('client/src/services/api.js', 'r') as f:
    content = f.read()

# Add credentials: 'include'
old_fetch = """
    const response = await fetch(`${BASE_URL}${endpoint}`, {
      ...fetchOptions,
      signal: controller.signal,
      headers: {
        Accept: 'application/json',
        ...(fetchOptions.headers || {}),
      },
    });
"""

new_fetch = """
    const response = await fetch(`${BASE_URL}${endpoint}`, {
      credentials: 'include',
      ...fetchOptions,
      signal: controller.signal,
      headers: {
        Accept: 'application/json',
        ...(fetchOptions.headers || {}),
      },
    });
"""
content = content.replace(old_fetch.strip(), new_fetch.strip())

# Remove getAuthHeader
old_getAuthHeader = """
function getAuthHeader() {
  const token = localStorage.getItem('admin_token');
  return token ? { 'X-API-Key': token } : {};
}
"""
content = content.replace(old_getAuthHeader.strip(), "")

# Update adminLogin to not use localStorage
old_adminLogin = """
  async adminLogin(username, password) {
    const res = await fetchSafe('/api/v1/admin/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username, password }),
      bypassCircuit: true
    });
    if (res.data?.status === 'success') {
      localStorage.setItem('admin_token', res.data.token);
    }
    return res;
  },
"""

new_adminLogin = """
  async adminLogin(username, password) {
    return await fetchSafe('/api/v1/admin/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username, password }),
      bypassCircuit: true
    });
  },
  
  async adminLogout() {
    return await fetchSafe('/api/v1/admin/logout', { method: 'POST', bypassCircuit: true });
  },
  
  async verifyAdmin() {
    return await fetchSafe('/api/v1/admin/me', { bypassCircuit: true });
  },
"""
content = content.replace(old_adminLogin.strip(), new_adminLogin.strip())

# Remove ...getAuthHeader() from CRUD methods
content = content.replace("...getAuthHeader()", "")
content = content.replace("headers: { 'Content-Type': 'application/json',  }", "headers: { 'Content-Type': 'application/json' }")
content = content.replace("headers: {  }", "")

with open('client/src/services/api.js', 'w') as f:
    f.write(content)
