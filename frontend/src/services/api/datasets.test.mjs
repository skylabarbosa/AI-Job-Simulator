import assert from 'node:assert/strict'
import test from 'node:test'

import { ApiError } from './client.ts'
import { formatDatasetErrorMessage } from './datasets.ts'

test('formatDatasetErrorMessage handles network and CORS failures', () => {
  const networkError = new ApiError('Failed to fetch', { isNetworkError: true })
  assert.equal(
    formatDatasetErrorMessage(networkError, 'fallback'),
    'Unable to connect to the backend server. Please verify your network connection or that the server is running.',
  )

  const rawFetchError = new TypeError('Failed to fetch')
  assert.equal(
    formatDatasetErrorMessage(rawFetchError, 'fallback'),
    'Unable to connect to the backend server. Please verify the backend is running.',
  )
})

test('formatDatasetErrorMessage handles unauthorized states', () => {
  const unauth401 = new ApiError('Authentication is required', { status: 401 })
  assert.equal(
    formatDatasetErrorMessage(unauth401, 'fallback'),
    'You do not have permission to access project resources. Please check your credentials.',
  )

  const forbidden403 = new ApiError('Forbidden', { status: 403 })
  assert.equal(
    formatDatasetErrorMessage(forbidden403, 'fallback'),
    'You do not have permission to access project resources. Please check your credentials.',
  )
})

test('formatDatasetErrorMessage handles 404, 409, and 500 statuses', () => {
  const notFound404 = new ApiError('Not found', { status: 404 })
  assert.equal(formatDatasetErrorMessage(notFound404, 'fallback'), 'Project resources were not found.')

  const conflict409 = new ApiError('Conflict', { status: 409 })
  assert.equal(
    formatDatasetErrorMessage(conflict409, 'fallback'),
    'Project blueprint is not approved for resource access.',
  )

  const serverError500 = new ApiError('Internal Error', { status: 500, detail: 'Storage bucket offline' })
  assert.equal(
    formatDatasetErrorMessage(serverError500, 'fallback'),
    'Backend error: Storage bucket offline',
  )
})

test('formatDatasetErrorMessage falls back gracefully for unknown errors', () => {
  assert.equal(formatDatasetErrorMessage(null, 'default error'), 'default error')
  assert.equal(formatDatasetErrorMessage(new Error('Custom specific issue'), 'fallback'), 'Custom specific issue')
})
