# ![Base](../assets/blockchains/base.png){ width="40px" } Base

Base is an Ethereum Layer 2 solution launched in 2023 by Coinbase, designed to bring the next billion users to Web3 through mainstream adoption.
XSHOT provides comprehensive trading features on Base through BaseSwap and Uniswap.

## Overview

=== "Technology"
    Built using the OP Stack in collaboration with Optimism, Base leverages Optimistic Rollups to provide fast, low-cost transactions while maintaining Ethereum's security guarantees.

=== "Foundation & Support"
    - Developed by Coinbase, a NASDAQ-listed cryptocurrency exchange
    - Backed by the Optimism Collective
    - Strong integration with Coinbase's ecosystem
    - Major institutional partnerships

=== "Market Position"
    - Rapidly growing Layer 2 solution
    - Integration with Coinbase's 100M+ users
    - Significant developer adoption
    - Growing DeFi ecosystem

## Key Advantages

- **Security**: Built on proven Optimism technology
- **Integration**: Seamless Coinbase connection
- **Cost**: Significantly lower fees than Ethereum
- **Speed**: Fast transaction finality
- **Accessibility**: Easy onboarding for new users

---

## Trading Features

=== "Available Trading Types"
    - [Market Buy](../features/trading/buying.md)
    - [Market Sell](../features/trading/selling.md)
    - [Limit Buy](../features/trading/limit-orders.md)
    - [Limit Sell](../features/trading/limit-orders.md)

=== "Unique Features"
    - [Cross-Chain Bridging](../features/bridging.md)
    - [MEV Protection](../security/mev-protection.md)
    - Native Base gas optimization

!!! note "XCaller AI"
    Automated trading via XCaller AI is currently only available on Solana.

## Supported DEXes

### Current
- [![BaseSwap](../assets/dex/baseswap.png){ width="20px" } BaseSwap](https://baseswap.fi/)
- [![Uniswap](../assets/dex/uniswap.png){ width="20px" } Uniswap V3](https://app.uniswap.org/)

## Getting Started

=== "Wallet Setup"
    XSHOT automatically creates a Base wallet for you.

    [:octicons-rocket-24: Setup Guide](../getting-started/setup-guide.md){ .md-button }

=== "Funding"
    1. Select "BASE" in the [bot interface](../user-guide/interface-overview.md)
    2. Use the displayed deposit address
    3. Wait for confirmations (recommended: 2-3 blocks)

!!! warning "Gas Requirements"
    Keep sufficient ETH in your wallet for gas fees on Base. While fees are significantly lower than Ethereum mainnet, you still need ETH for transactions.

## Network Specifications

| Metric | Value | Notes |
|--------|-------|-------|
| Block Time | ~2 seconds | Fast finality |
| Transaction Fee | $0.01-0.05 | Low cost trading |
| Finality | ~12 seconds | Quick confirmations |
| Gas Token | ETH | Required for all transactions |
| Token Standard | ERC20 | Full EVM compatibility |

## Performance Features

=== "Gas Optimization"
    - Smart gas price estimation
    - Transaction priority settings
    - Custom gas limits
    - Optimized fees

=== "MEV Protection"
    - Anti-sandwich protection
    - Front-running mitigation
    - Slippage optimization

    [:octicons-shield-24: Learn More](../security/mev-protection.md){ .md-button }

=== "Cross-Chain Features"

    Support for bridging from and to ETH directly on XSHOT

    [:octicons-arrow-switch-24: See Bridging Guide](../features/bridging.md){ .md-button }

## Safety Features

- [MEV Protection](../security/mev-protection.md)
- [Slippage Control](../user-guide/slippage-settings.md)
- [Gas Fee Configuration](../user-guide/gas-fee-configuration.md)

## Official Resources { .tabbed-links }

=== "Base"
    - [Base Website](https://base.org)
    - [BaseScan](https://basescan.org)
    - [Base Bridge](https://bridge.base.org)

=== "DEXes"
    - [BaseSwap](https://baseswap.fi)
    - [Uniswap on Base](https://app.uniswap.org)

=== "XSHOT Docs"
    - [Trading Guide](../features/trading/buying.md)
    - [Limit Orders](../features/trading/limit-orders.md)
    - [Portfolio Management](../features/portfolio-management.md)
    - [Bridge Guide](../features/bridging.md)

!!! tip "Pro Tips"
    - Base offers significantly lower fees than Ethereum mainnet
    - Use limit orders for better price execution
    - Monitor [BaseScan](https://basescan.org) for network status

!!! warning "Important Notes"
    - Always keep ETH for gas fees
    - Verify contract addresses on [BaseScan](https://basescan.org)
    - Check token approval limits
