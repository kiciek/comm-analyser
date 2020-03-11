from sys import argv

# global parameters:
bytes_per_message = 8
end_of_message_timeout_ms = 30
silence_between_talk_ms_min = 198
silence_between_talk_ms_max = 400
response_timeout_ms = 250
fast_response_timeout_ms = 229


class Message:
    """8 byte long frame with timestamp"""
    def __init__(self, timestamp, data):
        self.timestamp = timestamp
        self.data = data

    def __str__(self):
        return '{:>8}'.format(str(self.timestamp))+' '+format(self.data, ' 02X')

    def __repr__(self):
        return str(self)

    def __eq__(self,message):
        return self.data == message.data
        
    def __ne__(self,message):
        return self.data != message.data


def read_line(line):
    """
    :param line: csv line Build of:
    timestamp, some string, value
    example:
    "0.384060000000000,Async Serial,0xFF"

    :return: pair of timestamp, value
    """
    x = line.rstrip().split(',')
    timestamp = int(float(x[0])*1000)
    try:
        value = int(x[2], 16)
    except ValueError:
        value = int(x[2][:4], 16)
        print(x[2][4:], 'at: ', timestamp)
    return timestamp, value


def generate_message_list(filename):
    """
    restriction: responses are expected to have the same lenght as request ( this can be changed in future)
    :param filename: CSV file with communication log.
    :return: list of pairs [timestamp, `bytes_per_message` byte message]
     message may be shorter if something went unexpected during communication
    """
    messages = []
    with open(filename) as f:
        lines = f.readlines()
    j = 1
    while j < len(lines):
        timestamp, val = read_line(lines[j])
        old_stamp = timestamp
        for i in range(1, bytes_per_message):
            j += 1
            try:
                stamp, val2 = read_line(lines[j])
            except IndexError:
                print('broken message at the end: ', old_stamp)
                messages.append(Message(timestamp, val))
                break
            if (stamp - old_stamp) > end_of_message_timeout_ms:
                print('broken message at: ', stamp)
                messages.append(Message(timestamp, val))
                # j -= 1
                break
            val = (val << 8) + val2
            old_stamp = stamp
        else:
            messages.append(Message(timestamp, val))
            # print(messages)
            j += 1
    # data_file.close()
    return messages


def group_messages(grouped_list, message_list, i):
    """
    Pair, or pair(??) in triplets reguest, response [second response]
    Pardon silly recognition between 2 and 3 long groups, but it was ok for the task.
    :param grouped_list: [output]
    :param message_list: [source]
    :param i: starting point
    :return: messages grouped
    """
    # i += 1
    while i < len(message_list):
        if message_list[i].timestamp - message_list[i-1].timestamp > silence_between_talk_ms_max or \
           message_list[i].timestamp - message_list[i-1].timestamp < silence_between_talk_ms_min:
            print('timing error on time[s]:', message_list[i].timestamp)
            print('time from last frame equals:', message_list[i].timestamp - message_list[i-1].timestamp)
            grouped_list.append([message_list[i]])
        # 1 in row
        elif message_list[i].timestamp - message_list[i-1].timestamp > response_timeout_ms:
            grouped_list.append([message_list[i]])
        # 2 in row
        elif message_list[i].timestamp - message_list[i-1].timestamp < fast_response_timeout_ms:
            grouped_list.append([message_list[i-1], message_list[i]])
            i += 1
            # errors come from here
        # 3 in row
        else:
            try:
                grouped_list.append([message_list[i-1], message_list[i], message_list[i+1]])
                i += 2
            except IndexError:
                print('received only 2 of 3 messages')
                return i
        i += 1
    return i
   
   
def print_grouped_messages(grouped_list, i):
    """
    finds if any group differs from previous one, and point it out.
    :param grouped_list: list of single (in case of request only), double [request + response],
     or triple [request + 2 responses] [timestamp, messages] to analyse.
    :param i: starting point
    :return:
    """
    print('{:>4}'.format('0'), grouped_list[i])
    i += 1
    # http://stackoverflow.com/questions/12638408/decorating-hex-function-to-pad-zeros
    while i < len(grouped_list):
        if len(grouped_list[i]) == len(grouped_list[i-1]) and \
           grouped_list[i][0] == grouped_list[i-1][0] and grouped_list[i][1] == grouped_list[i-1][1] and \
           (len(grouped_list[i]) == 2 or grouped_list[i][2] == grouped_list[i-1][2]):
            pass
        else:
            # print(i-1, grouped_list[i-1])
            print('{:>4}'.format(i), grouped_list[i])
            if len(grouped_list[i]) == 3 and len(grouped_list[i-1]) == 3:
                    print('{0:{1}X}'.format(grouped_list[i][0].data ^ grouped_list[i-1][0].data, 32),
                          '{0:{1}X}'.format(grouped_list[i][1].data ^ grouped_list[i-1][1].data, 27),
                          '{0:{1}X}'.format(grouped_list[i][2].data ^ grouped_list[i-1][2].data, 27))
            elif len(grouped_list[i]) == 1 or len(grouped_list[i-1]) == 1:
                        print('{0:{1}X}'.format(grouped_list[i][0].data ^ grouped_list[i-1][0].data, 32))
            elif len(grouped_list[i]) == 3 and len(grouped_list[i-1]) == 2:
                    print('{0:{1}X}'.format(grouped_list[i][0].data ^ grouped_list[i-1][0].data, 32),
                          '{0:{1}X}'.format(grouped_list[i][1].data ^ grouped_list[i][0].data, 27),
                          '{0:{1}X}'.format(grouped_list[i][2].data ^ grouped_list[i-1][1].data, 27))
            elif len(grouped_list[i]) == 2 and len(grouped_list[i-1]) == 3:
                        print('{0:{1}X}'.format(grouped_list[i][0].data ^ grouped_list[i-1][0].data, 32),
                              '{0:{1}X}'.format(grouped_list[i][1].data ^ grouped_list[i-1][2].data, 27))
            else:
                        print('{0:{1}X}'.format(grouped_list[i][0].data ^ grouped_list[i-1][0].data, 32),
                              '{0:{1}X}'.format(grouped_list[i][1].data ^ grouped_list[i-1][1].data, 27))
        i += 1
    return i-1


def main():
    script, filename = argv
    message_list = generate_message_list(filename)
    # http://stackoverflow.com/questions/252703/python-append-vs-extend
    list2 = []
    group_messages(list2, message_list, 1)
    print_grouped_messages(list2, 0)
    return 0

if __name__ == "__main__":
    main()
