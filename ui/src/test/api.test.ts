import { afterEach, describe, expect, it, vi } from 'vitest'
import { makeCampusErrandsAPIRequest, makeAuthenticatedCampusErrandsAPIRequest } from '../api/api'
import { CampusErrandsAPIError } from '../api/models'

afterEach(() => vi.unstubAllGlobals())

describe('Campus Errands API', () => {
  it('encodes path and repeated query fields without sending a GET body', async () => {
    const fetch = vi.fn().mockResolvedValue(Response.json({ items: [] }))
    vi.stubGlobal('fetch', fetch)
    await makeCampusErrandsAPIRequest(
      { id: 'a/b', status: ['open', 'done'], unused: undefined },
      { url: '/errands/:id', verb: 'GET', fieldMap: { id: 'path', status: 'query' } },
    )
    expect(fetch).toHaveBeenCalledWith('/api/errands/a%2Fb?status=open&status=done', expect.objectContaining({ method: 'GET' }))
    expect(fetch.mock.calls[0][1].body).toBeUndefined()
  })

  it('sends JSON and includes session cookies', async () => {
    const fetch = vi.fn().mockResolvedValue(new Response(null, { status: 204 }))
    vi.stubGlobal('fetch', fetch)
    expect(await makeCampusErrandsAPIRequest({ title: 'Collect lunch' }, { url: '/errands', verb: 'POST' })).toBeNull()
    expect(fetch.mock.calls[0][1]).toMatchObject({
      credentials: 'include', headers: { 'Content-Type': 'application/json' }, body: '{"title":"Collect lunch"}',
    })
  })

  it('rejects an expired access token without retrying or refreshing', async () => {
    const fetch = vi.fn().mockResolvedValueOnce(Response.json({}, { status: 401 }))
    const onUnauthenticated = vi.fn()
    vi.stubGlobal('fetch', fetch)
    await expect(makeAuthenticatedCampusErrandsAPIRequest(null, { url: '/private', verb: 'GET', retry: true }, { onUnauthenticated })).rejects.toMatchObject({ status: 401 })
    expect(fetch).toHaveBeenCalledOnce()
    expect(onUnauthenticated).toHaveBeenCalledOnce()
  })

  it('reports failed authentication without treating service failures as logout', async () => {
    const onUnauthenticated = vi.fn()
    vi.stubGlobal('fetch', vi.fn().mockImplementation(() => Promise.resolve(Response.json({}, { status: 401 }))))
    await expect(makeAuthenticatedCampusErrandsAPIRequest(null, { url: '/private', verb: 'GET' }, { onUnauthenticated })).rejects.toBeInstanceOf(CampusErrandsAPIError)
    expect(onUnauthenticated).toHaveBeenCalledOnce()
    onUnauthenticated.mockClear()
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(Response.json({}, { status: 503 })))
    await expect(makeAuthenticatedCampusErrandsAPIRequest(null, { url: '/private', verb: 'GET' }, { onUnauthenticated })).rejects.toMatchObject({ status: 503 })
    expect(onUnauthenticated).not.toHaveBeenCalled()
  })

  it('rejects an HTML fallback and does not send an already aborted request', async () => {
    const fetch = vi.fn().mockResolvedValue(new Response('<!doctype html><html></html>', { headers: { 'content-type': 'text/html' } }))
    vi.stubGlobal('fetch', fetch)
    await expect(makeCampusErrandsAPIRequest(null, { url: '/private', verb: 'GET' })).rejects.toMatchObject({ status: 502 })
    fetch.mockClear()
    const controller = new AbortController()
    controller.abort()
    await expect(makeCampusErrandsAPIRequest(null, { url: '/private', verb: 'GET' }, { signal: controller.signal })).rejects.toMatchObject({ name: 'AbortError' })
    expect(fetch).not.toHaveBeenCalled()
  })
})
