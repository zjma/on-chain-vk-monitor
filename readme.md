An example of the proposed layout of a prover cluster that describes VK rotation from `ceremony123` to `ceremony124`.

Diff from today.
- Prover pods no longer monitor the on-chain VK.
- Prover pods no longer load 2 VKs.
- There are a `Deployment`, a `Service`, a `HttpRoute`, a `HealthCheckPolicy`, a `HPA` per ceremony.
- An on-chain VK monitor is introduced to poll on-chain VK and update the latest prover endpoint.
