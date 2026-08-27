import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it } from 'vitest'

import App from './App'

afterEach(() => {
  cleanup()
})

describe('Project Argus Final app', () => {
  it('renders the final analytics console shell', () => {
    const client = new QueryClient({
      defaultOptions: {
        queries: { retry: false },
        mutations: { retry: false },
      },
    })

    render(
      <QueryClientProvider client={client}>
        <App />
      </QueryClientProvider>,
    )

    expect(screen.getByText('PROJECT ARGUS')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /CHAT/i })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /METHODOLOGY/i })).toBeInTheDocument()
    expect(screen.getByRole('radio', { name: /Simple mode/i })).toBeInTheDocument()
    expect(screen.getByRole('radio', { name: /Experience mode/i })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /RUN/i })).toBeInTheDocument()
    expect(screen.getByText('Watchlist')).toBeInTheDocument()
    expect(screen.getAllByText(/not a buy\/sell tool/i).length).toBeGreaterThan(0)
  })

  it('defaults to live CSE REST for the final market-open workflow', () => {
    const client = new QueryClient({
      defaultOptions: {
        queries: { retry: false },
        mutations: { retry: false },
      },
    })

    render(
      <QueryClientProvider client={client}>
        <App />
      </QueryClientProvider>,
    )

    expect(screen.getByRole('checkbox', { name: /demo/i })).not.toBeChecked()
    expect(screen.getByRole('radio', { name: /Simple mode/i })).toHaveAttribute('aria-checked', 'true')
    expect(screen.getByText('Live CSE REST')).toBeInTheDocument()
  })

  it('shows the empty state before an analysis response loads', () => {
    const client = new QueryClient({
      defaultOptions: {
        queries: { retry: false },
        mutations: { retry: false },
      },
    })

    render(
      <QueryClientProvider client={client}>
        <App />
      </QueryClientProvider>,
    )

    expect(screen.getAllByText(/Ask Argus to read the market/i).length).toBeGreaterThan(0)
  })

  it('opens methodology drawer and closes it with Escape', () => {
    const client = new QueryClient({
      defaultOptions: {
        queries: { retry: false },
        mutations: { retry: false },
      },
    })

    render(
      <QueryClientProvider client={client}>
        <App />
      </QueryClientProvider>,
    )

    fireEvent.click(screen.getAllByRole('button', { name: /METHODOLOGY/i })[0])
    expect(screen.getByRole('heading', { name: /Methodology/i })).toBeInTheDocument()

    fireEvent.keyDown(window, { key: 'Escape' })
    expect(screen.queryByRole('heading', { name: /Methodology/i })).not.toBeInTheDocument()
  })
})
