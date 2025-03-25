An example of the proposed layout of a prover cluster that describes VK rotation from `ceremony123` to `ceremony124`.

Diff from today.
- Prover pods no longer monitor the on-chain VK.
- Prover pods no longer load 2 proving keys.
- Every ceremony will have its own prover `Deployment`, `Service`, `HttpRoute`, `HealthCheckPolicy`, a `HPA`.
- An on-chain VK monitor is introduced to poll on-chain VK and update the latest prover endpoint.
