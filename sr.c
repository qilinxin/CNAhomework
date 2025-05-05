#include <stdlib.h>
#include <stdio.h>
#include <stdbool.h>
#include "emulator.h"
#include "sr.h"

/* ******************************************************************
   Go Back N protocol.  Adapted from J.F.Kurose
   ALTERNATING BIT AND GO-BACK-N NETWORK EMULATOR: VERSION 1.2

   Network properties:
   - one way network delay averages five time units (longer if there
   are other messages in the channel for SR), but can be larger
   - packets can be corrupted (either the header or the data portion)
   or lost, according to user-defined probabilities
   - packets will be delivered in the order in which they were sent
   (although some can be lost).

   Modifications:
   - removed bidirectional SR code and other code not used by prac.
   - fixed C style to adhere to current programming style
   - added SR implementation
**********************************************************************/

#define RTT  16.0       /* round trip time.  MUST BE SET TO 16.0 when submitting assignment */
#define WINDOWSIZE 6    /* the maximum number of buffered unacked packet
                          MUST BE SET TO 6 when submitting assignment */
#define SEQSPACE 12      /* the min sequence space for SR must be at least windowsize * 2 */
#define NOTINUSE (-1)   /* used to fill header fields that are not being used */

/* generic procedure to compute the checksum of a packet.  Used by both sender and receiver
   the simulator will overwrite part of your packet with 'z's.  It will not overwrite your
   original checksum.  This procedure must generate a different checksum to the original if
   the packet is corrupted.
*/
int ComputeChecksum(struct pkt packet)
{
  int checksum = 0;
  int i;

  checksum = packet.seqnum;
  checksum += packet.acknum;
  for ( i=0; i<20; i++ )
    checksum += (int)(packet.payload[i]);

  return checksum;
}

bool IsCorrupted(struct pkt packet)
{
  if (packet.checksum == ComputeChecksum(packet))
    return (false);
  else
    return (true);
}


/********* Sender (A) variables and functions ************/

static struct pkt buffer[WINDOWSIZE];  /* array for storing packets waiting for ACK */
static int windowfirst, windowlast;    /* array indexes of the first/last packet awaiting ACK */
static int windowcount;                /* the number of packets currently awaiting an ACK */
static int A_nextseqnum;               /* the next sequence number to be used by the sender */
static bool isAcked[WINDOWSIZE];       /* array to track which packet is isAcked   */

/* called from layer 5 (application layer), passed the message to be sent to other side */
void A_output(struct msg message)
{
  struct pkt sendpkt;
  int i;

  /* if not blocked waiting on ACK */
  if ( windowcount < WINDOWSIZE) {
    if (TRACE > 1)
      printf("----A: New message arrives, send window is not full, send new messge to layer3!\n");

    /* create packet */
    sendpkt.seqnum = A_nextseqnum;
    sendpkt.acknum = NOTINUSE;
    for ( i=0; i<20 ; i++ )
      sendpkt.payload[i] = message.data[i];
    sendpkt.checksum = ComputeChecksum(sendpkt);

    /* put packet in window buffer */
    /* windowlast will always be 0 for alternating bit; but not for GoBackN */
    windowlast = (windowlast + 1) % WINDOWSIZE;
    buffer[windowlast] = sendpkt;
    windowcount++;

    /* send out packet */
    if (TRACE > 0)
      printf("Sending packet %d to layer 3\n", sendpkt.seqnum);
    tolayer3 (A, sendpkt);

    /* start timer if first packet in window */
    if (windowcount == 1)
      starttimer(A,RTT);

    /* get next sequence number, wrap back to 0 */
    A_nextseqnum = (A_nextseqnum + 1) % SEQSPACE;
  }
  /* if blocked,  window is full */
  else {
    if (TRACE > 0)
      printf("----A: New message arrives, send window is full\n");
    window_full++;
  }
}


/* called from layer 3, when a packet arrives for layer 4
   In this practical this will always be an ACK as B never sends data.
*/
void A_input(struct pkt packet)
{
  /* Only process if packet is not corrupted */
  if (!IsCorrupted(packet))
  {
    if (TRACE > 0)
      printf("----A: uncorrupted ACK %d is received\n", packet.acknum);

    /* If this ACK number hasn’t been seen before */
    if (!isAcked[packet.acknum])
    {
      if (TRACE > 0)
        printf("----A: ACK %d is not a duplicate\n", packet.acknum);
      new_ACKs++;
      isAcked[packet.acknum] = true;

      /* If this ACK corresponds to the base of our window, slide window forward past all consecutively isAcked packets */
      if (packet.acknum == buffer[windowfirst].seqnum)
      {
        while (windowcount > 0 && isAcked[buffer[windowfirst].seqnum])
        {
          windowfirst = (windowfirst + 1) % WINDOWSIZE;
          windowcount--;
        }

       /* Stop the current timer and, if there are still unACKed packets in the window, restart it */
        stoptimer(A);
        if (windowcount > 0)
          starttimer(A, RTT);
      }
    }
    else if (TRACE > 0)
      printf("----A: duplicate ACK received, do nothing!\n");
  }
  else if (TRACE > 0)
    printf("----A: corrupted ACK is received, do nothing!\n");
}

/*
 * A_timerinterrupt
 *
 * This function is invoked when the timer for the earliest unacknowledged packet expires.
 * In Selective Repeat, we only retransmit the single timed‐out packet (the oldest in the window),
 * rather than the entire window as in Go‐Back‐N.
 */
void A_timerinterrupt(void)
{
  /*  Log the timeout event */
  if (TRACE > 0)
    printf("----A: time out,resend packets!\n");

  if(TRACE > 0)
    printf("---A: resending packet %d\n", buffer[windowfirst].seqnum);

  /* Identify and retransmit the oldest unACKed packet */
  tolayer3(A, buffer[windowfirst]);
  packets_resent++;

  /*  Restart the timer for the next pending packet if there is remain */
  if(windowcount > 0)
    starttimer(A, RTT);
}



/* the following routine will be called once (only) before any other */
/* entity A routines are called. You can use it to do any initialization */
void A_init(void)
{
  /* initialise A's window, buffer and sequence number */
  A_nextseqnum = 0;  /* A starts with seq num 0, do not change this */
  windowfirst = 0;
  windowlast = -1;   /* windowlast is where the last packet sent is stored.
		     new packets are placed in winlast + 1
		     so initially this is set to -1
		   */
  windowcount = 0;
}



/********* Receiver (B)  variables and procedures ************/

static int expectedseqnum; /* the sequence number expected next by the receiver */
static int B_nextseqnum;   /* the sequence number for the next packets sent by B */
static struct pkt recvBuffer[SEQSPACE]; /* The packets cache obtained from A */
static bool received[SEQSPACE]; /* array to track which packet is isAcked  */

/* called from layer 3, when a packet arrives for layer 4 at B*/
void B_input(struct pkt packet)
{
  struct pkt sendpkt;
  int i;

  // Check for corruption; remove order check
  if ((!IsCorrupted(packet)))
  {
    if (TRACE > 0)
      printf("----B: packet %d is correctly received, send ACK!\n", packet.seqnum);
    packets_received++;

    /* Buffer the packet if it has not been seen before */
    if(received[packet.seqnum] == false)
    {
      received[packet.seqnum] = true;
      for(i = 0; i < 20; i++)
        recvBuffer[packet.seqnum].payload[i] = packet.payload[i];
    }

    /*  Deliver all consecutively received packets starting at expectedseqnum
    while(received[expectedseqnum] == true)
    {
      tolayer5(B, packet.payload);
      received[expectedseqnum] = false;
      expectedseqnum = (expectedseqnum + 1) % SEQSPACE;
    }

    /*  Construct ACK packet for the received sequence number */
    sendpkt.acknum = packet.seqnum;
    sendpkt.seqnum = NOTINUSE;
    for(i = 0; i < 20; i++)
      sendpkt.payload[i] = '0';

    sendpkt.checksum = ComputeChecksum(sendpkt);

    /*  Send ACK back to sender */
    tolayer3(B, sendpkt);
  }
}

/* the following routine will be called once (only) before any other */
/* entity B routines are called. You can use it to do any initialization */
void B_init(void)
{
  expectedseqnum = 0;
  B_nextseqnum = 1;
}

/******************************************************************************
 * The following functions need be completed only for bi-directional messages *
 *****************************************************************************/

/* Note that with simplex transfer from a-to-B, there is no B_output() */
void B_output(struct msg message)
{
}

/* called when B's timer goes off */
void B_timerinterrupt(void)
{
}
