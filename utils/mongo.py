import logging
import collections

class Document:
    def __init__(self, connection, document_name):
        self.db = connection[document_name]
        self.logger = logging.getLogger(__name__)

    async def update(self, dict):
        """ Pointer method: for simple update calls """
        await self.update_by_id(dict)

    async def get_by_id(self, id):
        """ Pointer method: similar to find_by_id """
        return await self.find_by_id(id)

    async def find(self, id):
        """ Pointer method: for simple find calls """
        return await self.find_by_id(id)

    async def delete(self, id):
        """ Pointer method: for simple delete calls"""
        await self.delete_by_id(id)

    async def find_by_id(self, id):
        " Returns the data found under 'id' "
        return await self.db.find_one({"_id": id})

    async def delete_by_id(self, id):
        """ Deletes all items found under 'id' """
        if not await self.find_by_id(id):
            pass
        await self.db.delete_many({"_id": id})

    async def insert(self, dict):
        """ Insert something into the db """
        if not isinstance(dict, collections.abc.Mapping):
            raise TypeError("Expected Dictionary.")
        
        if not dict["_id"]:
            raise KeyError("_id not found in supplied dict")

        await self.db.insert_one(dict)

    async def upsert(self, dict):
        """ Makes a new item in the document, if it already exists it will update instead """
        if await self.__get_raw(dict["_id"]) is not None:
            await self.update_by_id(dict)
        else:
            await self.db.insert_one(dict)

    async def update_by_id(self, dict):
        """ Updates existing data in document"""
        if not isinstance(dict, collections.abc.Mapping):
            raise TypeError("Expected Dictionary.")

        if not dict["_id"]:
            raise KeyError("_id not found in supplied dict.")

        if not await self.find_by_id(dict["_id"]):
            return

        id = dict["_id"]
        dict.pop("_id")
        await self.db.update_one({"_id": id}, {"$set": dict})

    async def unset(self, dict):
        """ Remove a field from existing document in collection """
        if not isinstance(dict, collections.abc.Mapping):
            raise TypeError("Expected Dictionary.")

        if not dict["_id"]:
            raise KeyError("_id not found in supplied dict.")

        if not await self.find_by_id(dict["_id"]):
            return

        id = dict["_id"]
        dict.pop("_id")
        await self.db.update_one({"_id": id}, {"$unset": dict})

    async def increment(self, id, amount, field):
        """ Increment a given field by a  given amount """
        if not await self.find_by_id(id):
            return

        self.db.update_one({"_id": id}, {"$inc": {field: amount}})

    async def get_all(self):
        """ Returns a list of all data in the document """
        data = []
        async for document in self.db.find({}):
            data.append(document)
        return data

    async def __get_raw(self, id):
        return await self.db.find_one({"_id": id})
