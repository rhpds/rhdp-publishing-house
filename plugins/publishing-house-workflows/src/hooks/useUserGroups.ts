import { useApi, identityApiRef } from '@backstage/core-plugin-api';
import useAsync from 'react-use/lib/useAsync';

export function useUserGroups() {
  const identityApi = useApi(identityApiRef);

  const { value, loading } = useAsync(async () => {
    const identity = await identityApi.getBackstageIdentity();
    const refs = identity.ownershipEntityRefs || [];
    return {
      isContentReviewer: refs.some(r => r === 'group:default/rhdp-content-review'),
      isInfraReviewer: refs.some(r => r === 'group:default/rhdp-infra-review'),
      isDeveloper: refs.some(r => r === 'group:default/rhdp-developers'),
      isContentDeveloper: refs.some(r => r === 'group:default/rhdp-content-developers'),
      isAdmin: refs.some(r => r === 'group:default/rhdp-administrators'),
    };
  }, []);

  return {
    isContentReviewer: value?.isContentReviewer ?? false,
    isInfraReviewer: value?.isInfraReviewer ?? false,
    isDeveloper: value?.isDeveloper ?? false,
    isContentDeveloper: value?.isContentDeveloper ?? false,
    isAdmin: value?.isAdmin ?? false,
    loading,
  };
}
