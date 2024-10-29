# ![BSC](../assets/blockchains/bnb.png){ width="40px" } Binance Smart Chain

Binance Smart Chain (BSC), launched in September 2020 by Binance, offers a high-performance, EVM-compatible blockchain designed for the mass market.
XSHOT provides comprehensive trading features on BSC through PancakeSwap.

## Overview

=== "Technology"
    BSC operates on a Proof of Staked Authority (PoSA) consensus mechanism, combining the benefits of delegated Proof of Stake and Proof of Authority for efficient block production and validation.

=== "Foundation & Support"
    - Created by Binance, the world's largest cryptocurrency exchange
    - Supported by the BNB Chain ecosystem fund
    - Strong backing from CZ (Changpeng Zhao) and team
    - Significant institutional integration

=== "Market Position"
    - Among top 3 blockchains by daily transactions
    - Multi-billion dollar TVL across DeFi protocols
    - Home to PancakeSwap, one of the largest DEXs
    - Strong retail user adoption

## Key Advantages

- **Low Fees**: Transactions typically cost cents
- **Speed**: 3-second block time
- **Compatibility**: Full EVM support
- **Accessibility**: Easy fiat on/off ramps
- **Ecosystem**: Rich DeFi and GameFi ecosystem

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
    - Native BNB gas optimization

!!! note "XCaller AI"
    Automated trading via XCaller AI is currently only available on Solana.

## Supported DEXes

### Current
- [![PancakeSwap](../assets/dex/pancakeswap.png){ width="20px" } PancakeSwap](https://pancakeswap.finance/)

## Getting Started

=== "Wallet Setup"
    XSHOT automatically creates a BSC wallet for you.

    [:octicons-rocket-24: Setup Guide](../getting-started/setup-guide.md){ .md-button }

=== "Funding"
    1. Select "BSC" in the [bot interface](../user-guide/interface-overview.md)
    2. Use the displayed deposit address
    3. Wait for confirmations (recommended: 2-3 blocks)

!!! warning "Gas Requirements"
    Keep sufficient BNB in your wallet for gas fees. Although fees are lower than Ethereum, you still need BNB for transactions.

## Network Specifications

| Metric | Value | Notes |
|--------|-------|-------|
| Block Time | ~3 seconds | Fast finality |
| Transaction Fee | $0.1-0.3 | Low cost trading |
| Finality | ~15 seconds | Quick confirmations |
| Gas Token | BNB | Required for all transactions |
| Token Standard | BEP20 | ERC20-compatible |

## Performance Features

=== "Gas Optimization"
    - Smart gas price estimation
    - Transaction priority settings
    - Custom gas limits
    - Low fee environment

=== "MEV Protection"
    - Anti-sandwich protection
    - Front-running mitigation
    - Slippage optimization

=== "Cross-Chain Features"
    Support for bridging from and to any L1 soon.
    [:octicons-arrow-switch-24: See Bridging Guide](../features/bridging.md){ .md-button }

## Safety Features

- [MEV Protection](../security/mev-protection.md)
- [Slippage Control](../user-guide/slippage-settings.md)
- [Gas Fee Configuration](../user-guide/gas-fee-configuration.md)

## Official Resources { .tabbed-links }

=== "BSC"
    - [BSC Website](https://www.bnbchain.org/)
    - [BscScan](https://bscscan.com/)
    - [Binance Bridge](https://www.bnbchain.org/bridge)

=== "DEX"
    - [PancakeSwap](https://pancakeswap.finance/)
    - [PancakeSwap Docs](https://docs.pancakeswap.finance/)

=== "XSHOT Docs"
    - [Trading Guide](../features/trading/buying.md)
    - [Limit Orders](../features/trading/limit-orders.md)
    - [Portfolio Management](../features/portfolio-management.md)
    - [Bridge Guide](../features/bridging.md)

!!! tip "Pro Tips"
    - BNB Chain offers some of the lowest fees in DeFi
    - Use limit orders for better price execution
    - Monitor [BscScan](https://bscscan.com) for network status

!!! warning "Important Notes"
    - Always keep BNB for gas fees
    - Verify contract addresses on [BscScan](https://bscscan.com)
    - Check token approval limits
