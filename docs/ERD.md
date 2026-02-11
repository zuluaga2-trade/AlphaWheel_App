# AlphaWheel Pro — Esquema de Base de Datos (ERD)

## Diagrama Entidad-Relación (Descripción)

```
┌─────────────────┐       ┌─────────────────────────────────────────────┐
│     User        │       │                  Account                     │
├─────────────────┤       ├─────────────────────────────────────────────┤
│ user_id (PK)    │──1:N──│ account_id (PK)                              │
│ email           │       │ user_id (FK)                                 │
│ display_name    │       │ name (ej. "Robinhood Taxable", "IRA")        │
│ created_at      │       │ provider ('tradier')                         │
└─────────────────┘       │ access_token (token API, actualizable)      │
                          │ environment ('sandbox' | 'prod')             │
                          │ cap_total, target_ann, max_per_ticker        │
                          │ connection_status ('online' | 'offline')     │
                          │ connection_checked_at                        │
                          │ created_at                                  │
                          └──────────────────┬──────────────────────────┘
                                             │
                    ┌────────────────────────┼────────────────────────┐
                    │ 1:N                    │ 1:N                    │ 1:N
                    ▼                        ▼                        ▼
┌──────────────────────────────┐  ┌─────────────────────┐  ┌──────────────────────┐
│          Trade               │  │      Dividend       │  │  PositionAdjustment  │
├──────────────────────────────┤  ├─────────────────────┤  ├──────────────────────┤
│ trade_id (PK)                │  │ dividend_id (PK)    │  │ adjustment_id (PK)   │
│ account_id (FK)              │  │ account_id (FK)     │  │ account_id (FK)      │
│ ticker                       │  │ ticker              │  │ trade_id (FK) null   │
│ asset_type ('OPTION'|'STOCK')│  │ amount              │  │ ticker               │
│ quantity                     │  │ ex_date             │  │ adjustment_type      │
│ price                        │  │ pay_date            │  │   ('SPLIT'|'COST')   │
│ strike                       │  │ note                │  │ old_value, new_value │
│ expiration_date              │  │ created_at          │  │ note, created_at     │
│ strategy_type (CSP|CC|etc)   │  └─────────────────────┘  └──────────────────────┘
│ status ('OPEN'|'CLOSED')     │
│ entry_type                   │
│   ('OPENING'|'ASSIGNMENT'|   │  ┌─────────────────────┐
│    'DIRECT_PURCHASE'|'CLOSING')│  │   TradeComment      │  (Bitácora)
│ trade_date                   │  ├─────────────────────┤
│ closed_date                  │  │ comment_id (PK)     │
│ parent_trade_id (FK) self    │──│ trade_id (FK)       │
│ comment (bitácora "por qué") │  │ body (texto)        │
│ created_at                   │  │ created_at          │
└──────────────────────────────┘  └──────────────────────┘
```

## Reglas de aislamiento

- **Todas** las consultas de datos operativos deben filtrar por `user_id` (vía `Account.user_id`) o por `account_id` perteneciente al usuario actual.
- Un usuario solo puede ver y gestionar sus propias cuentas y todos los registros asociados (Trades, Dividends, Adjustments).

## Entidades

| Entidad | Descripción |
|--------|-------------|
| **User** | Usuario del sistema. Puede tener varias cuentas. |
| **Account** | Cuenta de broker nombrada (ej. "Robinhood Taxable"). Contiene token del provider (Tradier). Una cuenta pertenece a un solo usuario. |
| **Trade** | Una pierna de operación: apertura/cierre de CSP, CC, compra/venta de acciones, asignación. `parent_trade_id` enlaza asignación con el CSP original. |
| **Dividend** | Dividendo recibido; impacta cost basis de la posición en ese ticker/cuenta. |
| **PositionAdjustment** | Ajuste manual: split, corrección de cost basis, etc. |
| **TradeComment** | Comentario de bitácora asociado a un trade ("por qué" del trade). |

## Índices recomendados

- `Account(user_id)`, `Trade(account_id)`, `Trade(status, account_id)`, `Trade(ticker, account_id)`
- `Dividend(account_id, ex_date)`, `PositionAdjustment(account_id)`
