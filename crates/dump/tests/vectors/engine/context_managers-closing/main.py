from contextlib import closing


class Connection:
    def send(self):
        pass

    def close(self):
        pass


with closing(Connection()) as conn:
    conn.send()
