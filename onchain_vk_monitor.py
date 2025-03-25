def fetch_onchain_vk():
    # TODO: ping https://fullnode.mainnet.aptoslabs.com/v1/accounts/0x1/resource/0x1::keyless_account::Groth16VerificationKey
    return 'ceremony124'


while True:
    ceremony_id = fetch_onchain_vk()
    httproute = k8scli.get_httproute('forward-to-latest')
    expected_backend = f'prover-{ceremony_id}'
    if httproute.spec.rules[0].backendRefs[0].name != expected_backend:
        httproute.spec.rules[0].backendRefs[0].name = expected_backend
        k8scli.apply(httproute)
