# ![Arbitrum](../assets/blockchains/arb.png){ width="40px" } Arbitrum

Arbitrum is a groundbreaking Layer 2 scaling solution for Ethereum, developed by Offchain Labs. Launched in 2021, it has rapidly become the leading Layer 2 network with over $9 billion in Total Value Locked (TVL) as of 2024.

## Overview

=== "Technology"
    Arbitrum uses Optimistic Rollups technology to achieve high throughput and low costs while inheriting Ethereum's security. Transactions are bundled and processed off-chain, then validated on Ethereum mainnet, resulting in significantly reduced fees and faster processing times.

=== "Foundation & Support"
    - Founded by Ed Felten, Steven Goldfeder, and Harry Kalodner
    - Backed by major institutions including Coinbase Ventures, Pantera Capital, and Lightspeed
    - Supported by a thriving ecosystem of 300+ protocols and applications

=== "Market Position"
    - Largest Ethereum L2 by TVL
    - Over 2 million active users
    - Home to major DeFi protocols like GMX, Camelot, and Uniswap
    - Native token $ARB widely distributed through airdrop

## Key Advantages

- **Cost Efficiency**: Transactions cost ~10x less than Ethereum mainnet
- **Speed**: 2-second block times with near-instant finality
- **Security**: Inherits Ethereum's robust security model
- **EVM Compatibility**: Seamless deployment of Ethereum applications
- **Ecosystem**: Rich DeFi ecosystem with major protocols and deep liquidity
## Trading Features

=== "Available Trading Types"
    - [Market Buy](../features/trading/buying.md)
    - [Market Sell](../features/trading/selling.md)
    - [Limit Buy](../features/trading/limit-orders.md)
    - [Limit Sell](../features/trading/limit-orders.md)

=== "Unique Features"
    - [Cross-Chain Bridging](../features/bridging.md)
    - [MEV Protection](../security/mev-protection.md)
    - Native Arbitrum gas optimization

!!! note "XCaller AI"
    Automated trading via XCaller AI is currently only available on Solana.

## Supported DEXes

### Current
- [![Camelot](../assets/dex/camelot.png){ width="20px" } Camelot](https://app.camelot.exchange)
- [![Uniswap](../assets/dex/uniswap.png){ width="20px" } Uniswap V3](https://app.uniswap.org)

## Getting Started

=== "Wallet Setup"
    XSHOT automatically creates an Arbitrum wallet for you.

    [:octicons-rocket-24: Setup Guide](../getting-started/setup-guide.md){ .md-button }

=== "Funding"
    1. Select "ARBITRUM" in the [bot interface](../user-guide/interface-overview.md)
    2. Use the displayed deposit address
    3. Wait for confirmations (recommended: 2-3 blocks)

!!! warning "Gas Requirements"
    Keep sufficient ETH in your wallet for gas fees on Arbitrum. While fees are significantly lower than Ethereum mainnet, you still need ETH for transactions.

## Network Specifications

| Metric | Value | Notes |
|--------|-------|-------|
| Block Time | ~2 seconds | Fast finality |
| Transaction Fee | $0.1-0.5 | Low cost trading |
| Finality | ~12 seconds | Quick confirmations |
| Gas Token | ETH | Required for all transactions |
| Token Standard | ERC20 | Full EVM compatibility |

## Performance Features

=== "Gas Optimization"
    - Smart gas price estimation
    - Transaction priority settings
    - Custom gas limits
    - L2 optimized fees

=== "MEV Protection"
    - Anti-sandwich protection
    - Front-running mitigation
    - Slippage optimization

=== "Cross-Chain Features"
    Support for bridging from and to ETH.

    [:octicons-arrow-switch-24: See Bridging Guide](../features/bridging.md){ .md-button }

## Safety Features

- [MEV Protection](../security/mev-protection.md)
- [Slippage Control](../user-guide/slippage-settings.md)
- [Gas Fee Configuration](../user-guide/gas-fee-configuration.md)

## Official Resources { .tabbed-links }

=== "Arbitrum"
    - [Arbitrum Website](https://arbitrum.io)
    - [Arbiscan](https://arbiscan.io)
    - [Arbitrum Bridge](https://bridge.arbitrum.io)

=== "DEXes"
    - [Camelot](https://app.camelot.exchange)
    - [Uniswap on Arbitrum](https://app.uniswap.org)

=== "XSHOT Docs"
    - [Trading Guide](../features/trading/buying.md)
    - [Limit Orders](../features/trading/limit-orders.md)
    - [Portfolio Management](../features/portfolio-management.md)
    - [Bridge Guide](../features/bridging.md)

!!! tip "Pro Tips"
    - Arbitrum offers significantly lower fees than Ethereum mainnet
    - Use limit orders for better price execution
    - Monitor [Arbiscan](https://arbiscan.io) for network status

!!! warning "Important Notes"
    - Always keep ETH for gas fees
    - Verify contract addresses on [Arbiscan](https://arbiscan.io)
    - Check token approval limits
