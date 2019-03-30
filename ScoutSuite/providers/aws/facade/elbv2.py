import asyncio

from ScoutSuite.providers.aws.facade.utils import AWSFacadeUtils
from ScoutSuite.providers.aws.facade.basefacade import AWSBaseFacade
from ScoutSuite.providers.aws.utils import ec2_classic
from ScoutSuite.providers.utils import run_concurrently


class ELBv2Facade(AWSBaseFacade):
    regional_load_balancers_cache_locks = {}
    load_balancers_cache = {}

    async def get_load_balancers(self, region: str, vpc: str):
        await self.cache_load_balancers(region)
        return [load_balancer for load_balancer in self.load_balancers_cache[region] if load_balancer['VpcId'] == vpc]

    async def cache_load_balancers(self, region):
        async with self.regional_load_balancers_cache_locks.setdefault(region, asyncio.Lock()):
            if region in self.load_balancers_cache:
                return

            self.load_balancers_cache[region] =\
                await AWSFacadeUtils.get_all_pages('elbv2', region, self.session,
                                                   'describe_load_balancers', 'LoadBalancers')

            for load_balancer in self.load_balancers_cache[region]:
                load_balancer['VpcId'] =\
                    load_balancer['VpcId'] if 'VpcId' in load_balancer and load_balancer['VpcId'] else ec2_classic

            await AWSFacadeUtils.get_and_set_concurrently(
                [self._get_and_set_load_balancer_attributes], self.load_balancers_cache[region], region=region)

    async def _get_and_set_load_balancer_attributes(self, load_balancer: dict, region: str):
        elbv2_client = AWSFacadeUtils.get_client('elbv2', self.session, region)
        load_balancer['attributes'] = await run_concurrently(
            lambda: elbv2_client.describe_load_balancer_attributes(
                LoadBalancerArn=load_balancer['LoadBalancerArn'])['Attributes']
        )

    async def get_listeners(self, region: str, load_balancer_arn: str):
        return await AWSFacadeUtils.get_all_pages(
            'elbv2', region, self.session, 'describe_listeners', 'Listeners', LoadBalancerArn=load_balancer_arn)
