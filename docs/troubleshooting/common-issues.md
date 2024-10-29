# 🔧 Common Issues & Quick Fixes

## Transaction Failed? Let's Fix It!

### Method 1: Adjust Gas Settings (Try This First)



1. 🏠 Go to main menu
2. ⚙️ Click "Chain Settings" (bottom right)
3. ⛽ Select "GAS SETTINGS"

![Chain Settings](../assets/main_interface/main_menu.png){ .screenshot-shadow }

![Gas Settings](../assets/buy_sell/chain_settings.png){ .screenshot-shadow }

=== "Step 1: Try HIGH"

    - Click "HIGH" option
    - Attempt transaction again

=== "Step 2: Try CUSTOM"
    If HIGH doesn't work:

    - Select "CUSTOM"
    - Set value higher than HIGH
    - Try transaction again

!!! tip "💡 Gas Tip"
    Start with HIGH setting before using CUSTOM values

![Gas Settings](../assets/buy_sell/change_fees.png){ .screenshot-shadow }

### Method 2: Increase Slippage

If gas adjustment didn't help:

![Buy Menu](../assets/buy_sell/buy_menu.png){ .screenshot-shadow }

1. 🎯 In buy screen
2. ⚙️ Disable "auto" slippage
3. 📊 Set custom value higher than current
4. 🔄 Try transaction again

!!! warning "Important"
    Always start with gas adjustment before changing slippage

### Quick Resolution Guide

```mermaid
graph TD
    A[Transaction Failed] --> B{Change Gas fees setting}
    B -->|Step 1| C[Use HIGH Gas]
    C -->|Failed| D[Use CUSTOM Gas]
    D -->|Failed| E[Increase Slippage]
    C -->|Success| F[Done!]
    D -->|Success| F
    E -->|Success| F
    style A fill:#ff6b6b,stroke:#fff
    style F fill:#51cf66,stroke:#fff
```

!!! success "🎯 Resolution Steps"
    1. First try HIGH gas
    2. Then try CUSTOM gas (higher value)
    3. Finally adjust slippage if needed

## Still Having Issues?

Need more help? We're here for you:

[📱 Support Channel](https://t.me/Xshot_trading){ .md-button .md-button--primary }
[👥 Main Community](https://t.me/xerc20){ .md-button }

