"""Local-only administrative bootstrap. Does not create any operational data."""
import asyncio
import getpass
from core import db, indexes, audit
from auth import create_user
from models import Register


async def main():
    await indexes()
    if await db.users.find_one({'role': 'super_admin'}):
        print('Super Admin already exists; no changes made.')
        return
    email = input('Super Admin email: ').strip()
    mobile = input('Mobile with country code: ').strip()
    name = input('Name: ').strip()
    password = getpass.getpass('Password (12+ characters): ')
    user = await create_user(Register(email=email, mobile=mobile, name=name, password=password), 'super_admin')
    await audit(user, 'SUPER_ADMIN_BOOTSTRAPPED', user['id'])
    print('Super Admin created. Store the credentials securely.')


if __name__ == '__main__':
    asyncio.run(main())