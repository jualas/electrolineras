import { describe, expect, it } from 'vitest'

import { stationPopupHtml } from './stationLayers'

describe('stationPopupHtml', () => {
  it('escapa los datos externos de la estación (XSS)', () => {
    const html = stationPopupHtml({
      site_name: '<img src=x onerror=alert(1)>',
      operator: '<b>op</b>',
      address: '<script>alert(1)</script>',
      dynamic_status: 'x"><img src=x onerror=alert(1)>',
    })
    expect(html).not.toContain('<script>')
    expect(html).not.toContain('<img')
    expect(html).not.toContain('<b>')
    expect(html).toContain('&lt;script&gt;alert(1)&lt;/script&gt;')
  })
})
