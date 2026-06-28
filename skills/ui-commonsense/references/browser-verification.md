# Browser Verification Commonsense

Use this reference before claiming UI work is complete.

## Minimum Verification

- Verify the actual browser page, not just component code.
- Cover the viewport where the defect was reported.
- Exercise at least one real interaction path.
- Capture evidence as screenshot, DOM measurement, or Playwright assertion.

## Shared Shell And Navigation Verification

For a shared application shell, sidebar, topbar, or route navigation refactor, verify a route-by-viewport matrix instead of a single representative page.

- Cover every primary navigation route affected by the shared shell.
- Cover desktop and constrained/mobile viewports unless the reported defect is viewport-specific and narrower.
- Check active navigation state on the exact route and at least one nested route when nested routes share a parent nav item.
- Check persistent shell controls such as account identity, locale switcher, logout, primary navigation, and responsive navigation fallback.
- Record any page-specific overflow separately from shell defects. Do not treat a local wide table as fixed by adding broad shell scrolling.
- Keep evidence local to the actual route set: screenshots, DOM measurements, or Playwright assertions should name the routes and viewport sizes.

## What To Check

- Drawer content is not vertically stretched.
- No unwanted card-in-card structure remains.
- Numeric inputs use number controls and allow intended decimals.
- Units display with values, not names.
- Combobox search, select, and reopen behavior works.
- Dropdowns are not clipped and have sane z-index.
- Read-only values align with nearby inputs.
- Tables have headers when row comparison matters.
- Text does not overlap, truncate critical labels, or cause horizontal scroll.

## DOM Measurement Snippets

Check vertical alignment:

```js
const center = (el) => {
  const rect = el.getBoundingClientRect()
  return rect.top + rect.height / 2
}

Math.round(center(readOnlyValue) - center(input))
```

Check combobox reopen:

```js
await input.click()
await option.click()
await input.click()
const optionCount = await dropdownOptions.count()
```

Check drawer grid packing:

```js
form.className.includes('content-start')
```

Check same-row alignment:

```js
const a = firstControl.getBoundingClientRect()
const b = secondControl.getBoundingClientRect()
Math.abs(a.y - b.y) < 4
```

## Reporting

Report the concrete browser evidence:

- command or Playwright path used;
- observed count, class, bounding-box delta, or screenshot result;
- remaining visual risk if any viewport was not checked.

If the UI surface is component-only, report browser evidence as `not claimed` unless there is an actual route, Story, Dev Lab page, or other browser-accessible surface. Component tests can prove composition and states, but they are not screenshot or browser evidence for a runnable page.
