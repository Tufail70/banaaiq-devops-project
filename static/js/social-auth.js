/**
 * BanaaIQ — Social Login Redirect Handler
 * Replaces popup behavior with full redirect
 * Forces account selection on every login
 */

const SOCIAL_AUTH_CONFIG = {
  google: {
    authUrl: 'https://accounts.google.com/o/oauth2/v2/auth',
    params: {
      client_id: window.GOOGLE_CLIENT_ID || '',
      redirect_uri: window.location.origin
        + '/auth/google/callback',
      response_type: 'code',
      scope: 'openid email profile',
      prompt: 'select_account',
      access_type: 'offline'
    }
  },
  linkedin: {
    authUrl: 'https://www.linkedin.com/oauth/v2/authorization',
    params: {
      client_id: window.LINKEDIN_CLIENT_ID || '',
      redirect_uri: window.location.origin
        + '/auth/linkedin/callback',
      response_type: 'code',
      scope: 'r_liteprofile r_emailaddress',
      prompt: 'select_account'
    }
  }
}

/**
 * Redirects current window to social auth page
 * Forces account selection via prompt=select_account
 * @param {string} provider - 'google' or 'linkedin'
 */
function socialLoginRedirect(provider) {
  const config = SOCIAL_AUTH_CONFIG[provider]

  if (!config) {
    console.error(
      'Unknown provider:', provider
    )
    return
  }

  // Build query string with all params
  const params = new URLSearchParams(
    config.params
  )

  // Always force account selection
  params.set('prompt', 'select_account')

  // Add state for CSRF protection
  const state = Math.random()
    .toString(36)
    .substring(2, 15)
  sessionStorage.setItem(
    'oauth_state_' + provider, state
  )
  params.set('state', state)

  // Full redirect — no popup
  const authUrl = config.authUrl
    + '?' + params.toString()

  window.location.href = authUrl
}

/**
 * Google login button handler
 */
function loginWithGoogle() {
  socialLoginRedirect('google')
}

/**
 * LinkedIn login button handler
 */
function loginWithLinkedIn() {
  socialLoginRedirect('linkedin')
}

// Override any existing popup-based handlers
// when DOM is ready
document.addEventListener(
  'DOMContentLoaded', function() {

  // Find all Google login buttons
  const googleBtns = document.querySelectorAll(
    '[data-provider="google"],' +
    '.google-login-btn,' +
    '#google-login-btn,' +
    '[onclick*="google"]'
  )

  googleBtns.forEach(btn => {
    // Remove popup handlers
    btn.removeAttribute('onclick')
    btn.addEventListener('click', function(e) {
      e.preventDefault()
      e.stopPropagation()
      loginWithGoogle()
    })
  })

  // Find all LinkedIn login buttons
  const linkedinBtns = document.querySelectorAll(
    '[data-provider="linkedin"],' +
    '.linkedin-login-btn,' +
    '#linkedin-login-btn,' +
    '[onclick*="linkedin"]'
  )

  linkedinBtns.forEach(btn => {
    btn.removeAttribute('onclick')
    btn.addEventListener('click', function(e) {
      e.preventDefault()
      e.stopPropagation()
      loginWithLinkedIn()
    })
  })
})
