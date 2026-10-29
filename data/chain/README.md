# NHL Breakaway on-chain reference (Polygon)

- `contracts.json`: 156 ERC-721 contracts (symbol `BRKWY`): 93 moment-series contracts + 63 pack contracts.
  Per contract: name, symbol, contractURI, owner, interface flags (ERC721 / Enumerable / ERC2981), a sample tokenURI, royalty info and the collection-level metadata JSON.
- `pack_contracts.json`: pack contract → pack series, title, price, quantity, drop time, sample token id.

## Rules
- Token ID = (moment_index << 48) + (edition - 1)
- Moment UUID = 16-hex series prefix + 4-hex moment index + 12 zeros
- Pack tokens use the same scheme; pack index = pack_uuid[16:20]
- tokenURI = `ipfs://<CID>` (one CID per token); contractURI is hosted by the platform (nft.nhlbreakaway.com).
- Royalty (ERC2981): 600 bps (6%).
- Contracts are not enumerable and expose no totalSupply; supply figures come from the public stats API (see ../api_snapshot).
