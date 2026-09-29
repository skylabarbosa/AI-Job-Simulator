import assert from 'node:assert/strict'
import test from 'node:test'

import {
  authenticateAndLoadProfile,
  canAccessRole,
  loginRoleMismatchMessage,
  missingProfileMessage,
  resolveAuthenticatedProfile,
  signOutAndClear,
} from './profileResolution.ts'

const learner = { id: 'learner-uid', email: 'learner@example.test', display_name: 'Learner', role: 'learner' }
const business = { id: 'business-uid', email: 'business@example.test', display_name: 'Business', role: 'business' }

test('resolves an existing learner profile by authenticated UID', async () => {
  const profile = await resolveAuthenticatedProfile(learner.id, async (id) => ({
    data: id === learner.id ? learner : null,
    error: null,
  }))
  assert.equal(profile.role, 'learner')
})

test('resolves an existing business profile by authenticated UID', async () => {
  const profile = await resolveAuthenticatedProfile(business.id, async (id) => ({
    data: id === business.id ? business : null,
    error: null,
  }))
  assert.equal(profile.role, 'business')
})

test('links a recreated Auth UID to its matching profile, not a former identity', async () => {
  const formerUser = { ...business, id: 'deleted-business-uid' }
  const currentUserId = 'recreated-business-uid'
  const currentProfile = { ...business, id: currentUserId }
  let queriedId

  const profile = await resolveAuthenticatedProfile(currentUserId, async (id) => {
    queriedId = id
    return { data: id === currentProfile.id ? currentProfile : formerUser, error: null }
  })

  assert.equal(queriedId, currentUserId)
  assert.notEqual(queriedId, formerUser.id)
  assert.equal(profile.id, currentUserId)
  assert.equal(profile.role, 'business')
})

test('reports a selected login type that differs from the profile role', () => {
  assert.equal(
    loginRoleMismatchMessage('learner', 'business'),
    'This account is registered as a Business account. Please select Learner to continue.',
  )
  assert.equal(
    loginRoleMismatchMessage('business', 'learner'),
    'This account is registered as a Learner account. Please select Business to continue.',
  )
  assert.equal(loginRoleMismatchMessage('business', 'business'), null)
})

test('reports an authenticated user with no provisioned profile', async () => {
  await assert.rejects(
    resolveAuthenticatedProfile('missing-uid', async () => ({ data: null, error: null })),
    { message: missingProfileMessage },
  )
})

test('preserves Supabase password failures and does not attempt profile lookup', async () => {
  const invalidPassword = new Error('Invalid login credentials')
  let profileLookupCalled = false

  await assert.rejects(
    authenticateAndLoadProfile(
      async () => ({ data: { user: null, session: null }, error: invalidPassword }),
      () => assert.fail('An unauthenticated user must not be accepted.'),
      async () => {
        profileLookupCalled = true
        return learner
      },
    ),
    (error) => error === invalidPassword,
  )
  assert.equal(profileLookupCalled, false)
})

test('learner and business route authorization remain mutually exclusive', () => {
  assert.equal(canAccessRole('learner', ['learner']), true)
  assert.equal(canAccessRole('learner', ['business', 'admin']), false)
  assert.equal(canAccessRole('business', ['business', 'admin']), true)
  assert.equal(canAccessRole('business', ['learner']), false)
})

test('profile loading keeps authentication unresolved until the profile is available', async () => {
  let finishProfileLookup
  let completed = false
  const pendingProfile = new Promise((resolve) => { finishProfileLookup = resolve })
  const flow = authenticateAndLoadProfile(
    async () => ({ data: { user: { id: learner.id }, session: { access_token: 'session' } }, error: null }),
    () => {},
    async () => pendingProfile,
  ).then((profile) => {
    completed = true
    return profile
  })

  await Promise.resolve()
  assert.equal(completed, false)
  finishProfileLookup(learner)
  assert.equal((await flow).id, learner.id)
})

test('logout clears state and a subsequent login resolves the next user', async () => {
  let activeProfile = learner
  await signOutAndClear(
    async () => ({ error: null }),
    () => { activeProfile = null },
  )
  assert.equal(activeProfile, null)

  activeProfile = await authenticateAndLoadProfile(
    async () => ({ data: { user: { id: business.id }, session: { access_token: 'new-session' } }, error: null }),
    () => {},
    async (userId) => resolveAuthenticatedProfile(userId, async (id) => ({
      data: id === business.id ? business : null,
      error: null,
    })),
  )
  assert.equal(activeProfile.role, 'business')
})