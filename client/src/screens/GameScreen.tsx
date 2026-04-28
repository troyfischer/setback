import { StyleSheet, Text, View } from 'react-native';

import { ActionButton } from '../components/ActionButton';
import { PlayingCard } from '../components/PlayingCard';
import { formatCard, formatPhase, getCurrentTurnPlayer, getMyHand } from '../lib/format';
import type {
  CurrentUser,
  GameStatePlayerScoped,
  SetbackCard,
} from '../types/setback';

const BID_OPTIONS = [0, 2, 3, 4] as const;

type SubscriptionStatus = 'idle' | 'connecting' | 'live' | 'error';

type Props = {
  activeGameId: number;
  busyAction: string | null;
  currentUser: CurrentUser;
  error: string | null;
  gameState: GameStatePlayerScoped;
  notice: string | null;
  onBid: (amount: (typeof BID_OPTIONS)[number]) => void;
  onLeaveTable: () => void;
  onPlayCard: (card: SetbackCard) => void;
  streamStatus: SubscriptionStatus;
};

export function GameScreen({
  activeGameId,
  busyAction,
  currentUser,
  error,
  gameState,
  notice,
  onBid,
  onLeaveTable,
  onPlayCard,
  streamStatus,
}: Props) {
  const currentPlayer = getCurrentTurnPlayer(gameState);
  const myHand = getMyHand(gameState);
  const trump = gameState.active_round.trump;
  const trick = gameState.active_round.trick?.collection ?? [];
  const bidHistory = gameState.active_round.bid.collection;
  const scoreEntries = Object.entries(gameState.score);
  const isComplete = gameState.phase === 'complete';
  const yourTurn = currentPlayer?.player_id === currentUser.sub;
  const canPlay = gameState.phase === 'play' && yourTurn;

  return (
    <View style={styles.wrapper}>
      <View style={styles.header}>
        <View style={styles.headerLeft}>
          <Text style={styles.brand}>Setback</Text>
          <Text style={styles.subBrand}>
            Table #{activeGameId} · {formatPhase(gameState.phase)}
          </Text>
        </View>
        <View style={styles.headerRight}>
          <StreamIndicator status={streamStatus} />
          <ActionButton label="Leave" onPress={onLeaveTable} tone="ghost" />
        </View>
      </View>

      <View style={styles.scoreRow}>
        {scoreEntries.length > 0 ? (
          scoreEntries.map(([teamId, score]) => (
            <View key={teamId} style={styles.scoreTile}>
              <Text style={styles.scoreTeam}>Team {teamId}</Text>
              <Text style={styles.scoreValue}>{score}</Text>
            </View>
          ))
        ) : (
          <View style={styles.scoreTile}>
            <Text style={styles.scoreTeam}>Score</Text>
            <Text style={styles.scoreValue}>—</Text>
          </View>
        )}
        <View style={styles.scoreTile}>
          <Text style={styles.scoreTeam}>Target</Text>
          <Text style={styles.scoreValue}>{gameState.max_score}</Text>
        </View>
      </View>

      {error ? (
        <View style={[styles.banner, styles.errorBanner]}>
          <Text style={styles.bannerText}>{error}</Text>
        </View>
      ) : null}
      {notice && !error ? (
        <View style={[styles.banner, styles.noticeBanner]}>
          <Text style={styles.bannerText}>{notice}</Text>
        </View>
      ) : null}

      {isComplete ? (
        <View style={styles.resultCard}>
          <Text style={styles.resultEyebrow}>Final</Text>
          <Text style={styles.resultTitle}>Game over</Text>
          <View style={styles.resultScores}>
            {scoreEntries.map(([teamId, score]) => (
              <View key={teamId} style={styles.resultTile}>
                <Text style={styles.resultTeam}>Team {teamId}</Text>
                <Text style={styles.resultScore}>{score}</Text>
              </View>
            ))}
          </View>
          <ActionButton label="Back To Lobby" onPress={onLeaveTable} />
        </View>
      ) : (
        <>
          <View style={styles.card}>
            <View style={styles.roundRow}>
              <View style={styles.infoBlock}>
                <Text style={styles.infoLabel}>Trump</Text>
                <Text style={styles.infoValue}>
                  {trump ? capitalize(trump) : 'Not set'}
                </Text>
              </View>
              <View style={styles.infoBlock}>
                <Text style={styles.infoLabel}>Up next</Text>
                <Text style={styles.infoValue}>
                  {currentPlayer ? currentPlayer.player_id : 'Pending'}
                </Text>
                {yourTurn ? <Text style={styles.yourTurn}>Your turn</Text> : null}
              </View>
            </View>

            <View style={styles.playerList}>
              {gameState.order.order.map((player) => {
                const active = player.player_id === currentPlayer?.player_id;
                return (
                  <View
                    key={player.player_id}
                    style={[styles.playerChip, active ? styles.playerChipActive : null]}
                  >
                    <Text style={[styles.playerName, active ? styles.playerNameActive : null]}>
                      {player.player_id}
                    </Text>
                    <Text style={styles.playerTeam}>Team {player.team_id}</Text>
                  </View>
                );
              })}
            </View>
          </View>

          {trick.length > 0 ? (
            <View style={styles.card}>
              <Text style={styles.sectionTitle}>Current trick</Text>
              <View style={styles.trickRow}>
                {trick.map((card, index) => (
                  <PlayingCard
                    key={`${card.player_id}-${index}`}
                    card={card}
                    caption={card.player_id}
                  />
                ))}
              </View>
            </View>
          ) : null}

          {gameState.phase === 'bid' ? (
            <View style={styles.card}>
              <Text style={styles.sectionTitle}>Bidding</Text>
              <Text style={styles.sectionSubtitle}>
                Pass or bid how many points your team will take this round.
              </Text>
              <View style={styles.bidRow}>
                {BID_OPTIONS.map((amount) => (
                  <ActionButton
                    key={amount}
                    busy={busyAction === `Bid ${amount}`}
                    label={amount === 0 ? 'Pass' : `Bid ${amount}`}
                    onPress={() => onBid(amount)}
                    tone={amount === 0 ? 'ghost' : 'secondary'}
                  />
                ))}
              </View>

              {bidHistory.length > 0 ? (
                <View style={styles.bidHistory}>
                  <Text style={styles.sectionSubtitle}>This round:</Text>
                  {bidHistory.map((bid, index) => (
                    <Text key={`${bid.player_id}-${index}`} style={styles.bidHistoryItem}>
                      {bid.player_id} {bid.amount === 0 ? 'passed' : `bid ${bid.amount}`}
                    </Text>
                  ))}
                </View>
              ) : null}
            </View>
          ) : null}

          {myHand.length > 0 ? (
            <View style={styles.card}>
              <Text style={styles.sectionTitle}>Your hand</Text>
              <Text style={styles.sectionSubtitle}>
                {gameState.phase === 'bid'
                  ? 'Review your cards, then pass or bid.'
                  : canPlay
                    ? 'Tap a card to play it.'
                    : `Waiting on ${currentPlayer?.player_id ?? 'the next player'}.`}
              </Text>
              <View style={styles.handRow}>
                {myHand.map((card, index) => (
                  <PlayingCard
                    key={`${card.suit}-${card.value}-${index}`}
                    busy={busyAction === `Play ${formatCard(card)}`}
                    card={card}
                    disabled={!canPlay}
                    onPress={canPlay ? () => onPlayCard(card) : undefined}
                  />
                ))}
              </View>
            </View>
          ) : null}
        </>
      )}
    </View>
  );
}

function StreamIndicator({ status }: { status: SubscriptionStatus }) {
  const { dot, label } = streamLabel(status);
  return (
    <View style={styles.streamPill}>
      <View style={[styles.streamDot, { backgroundColor: dot }]} />
      <Text style={styles.streamText}>{label}</Text>
    </View>
  );
}

function streamLabel(status: SubscriptionStatus) {
  switch (status) {
    case 'live':
      return { dot: '#3cc98a', label: 'Live' };
    case 'connecting':
      return { dot: '#f7d774', label: 'Connecting' };
    case 'error':
      return { dot: '#d86b5a', label: 'Reconnecting' };
    default:
      return { dot: '#8ca3bf', label: 'Offline' };
  }
}

function capitalize(value: string): string {
  return value.charAt(0).toUpperCase() + value.slice(1);
}

const styles = StyleSheet.create({
  banner: {
    borderRadius: 14,
    paddingHorizontal: 16,
    paddingVertical: 12,
  },
  bannerText: {
    color: '#fdfefe',
    fontSize: 14,
    fontWeight: '600',
  },
  bidHistory: {
    backgroundColor: '#eff4fa',
    borderRadius: 14,
    padding: 12,
    rowGap: 4,
  },
  bidHistoryItem: {
    color: '#173152',
    fontSize: 13,
  },
  bidRow: {
    columnGap: 10,
    flexDirection: 'row',
    flexWrap: 'wrap',
    rowGap: 10,
  },
  brand: {
    color: '#f8fbff',
    fontSize: 22,
    fontWeight: '900',
    letterSpacing: 0.5,
  },
  card: {
    backgroundColor: '#fffaf2',
    borderRadius: 24,
    padding: 20,
    rowGap: 14,
    shadowColor: '#081120',
    shadowOffset: { height: 8, width: 0 },
    shadowOpacity: 0.18,
    shadowRadius: 20,
  },
  errorBanner: {
    backgroundColor: 'rgba(150, 45, 36, 0.94)',
  },
  handRow: {
    columnGap: 10,
    flexDirection: 'row',
    flexWrap: 'wrap',
    rowGap: 10,
  },
  header: {
    alignItems: 'center',
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 12,
    justifyContent: 'space-between',
  },
  headerLeft: {
    flexShrink: 1,
  },
  headerRight: {
    alignItems: 'center',
    columnGap: 10,
    flexDirection: 'row',
    flexWrap: 'wrap',
    rowGap: 8,
  },
  infoBlock: {
    flexGrow: 1,
    flexShrink: 1,
    minWidth: 140,
    rowGap: 2,
  },
  infoLabel: {
    color: '#5c7593',
    fontSize: 11,
    fontWeight: '700',
    letterSpacing: 1,
    textTransform: 'uppercase',
  },
  infoValue: {
    color: '#102947',
    fontSize: 20,
    fontWeight: '800',
  },
  noticeBanner: {
    backgroundColor: 'rgba(31, 134, 99, 0.92)',
  },
  playerChip: {
    backgroundColor: '#eff4fa',
    borderRadius: 14,
    paddingHorizontal: 12,
    paddingVertical: 10,
    rowGap: 2,
  },
  playerChipActive: {
    backgroundColor: '#102947',
  },
  playerList: {
    columnGap: 10,
    flexDirection: 'row',
    flexWrap: 'wrap',
    rowGap: 10,
  },
  playerName: {
    color: '#102947',
    fontSize: 14,
    fontWeight: '700',
  },
  playerNameActive: {
    color: '#f8fbff',
  },
  playerTeam: {
    color: '#5c7593',
    fontSize: 11,
    fontWeight: '600',
    textTransform: 'uppercase',
  },
  resultCard: {
    alignItems: 'center',
    backgroundColor: '#fffaf2',
    borderRadius: 28,
    padding: 28,
    rowGap: 14,
    shadowColor: '#081120',
    shadowOffset: { height: 10, width: 0 },
    shadowOpacity: 0.2,
    shadowRadius: 24,
  },
  resultEyebrow: {
    color: '#b54434',
    fontSize: 12,
    fontWeight: '800',
    letterSpacing: 1.6,
    textTransform: 'uppercase',
  },
  resultScore: {
    color: '#102947',
    fontSize: 30,
    fontWeight: '800',
    marginTop: 4,
  },
  resultScores: {
    columnGap: 14,
    flexDirection: 'row',
    flexWrap: 'wrap',
    justifyContent: 'center',
    rowGap: 14,
  },
  resultTeam: {
    color: '#5c7593',
    fontSize: 12,
    fontWeight: '700',
    textTransform: 'uppercase',
  },
  resultTile: {
    alignItems: 'center',
    backgroundColor: '#eff4fa',
    borderRadius: 18,
    minWidth: 120,
    paddingHorizontal: 16,
    paddingVertical: 14,
  },
  resultTitle: {
    color: '#102947',
    fontSize: 26,
    fontWeight: '800',
  },
  roundRow: {
    columnGap: 14,
    flexDirection: 'row',
    flexWrap: 'wrap',
    rowGap: 14,
  },
  scoreRow: {
    columnGap: 10,
    flexDirection: 'row',
    flexWrap: 'wrap',
    rowGap: 10,
  },
  scoreTeam: {
    color: '#9fb6d4',
    fontSize: 11,
    fontWeight: '700',
    letterSpacing: 1,
    textTransform: 'uppercase',
  },
  scoreTile: {
    backgroundColor: 'rgba(8, 17, 32, 0.55)',
    borderColor: 'rgba(247, 215, 116, 0.4)',
    borderRadius: 18,
    borderWidth: 1,
    flexGrow: 1,
    minWidth: 110,
    paddingHorizontal: 16,
    paddingVertical: 14,
  },
  scoreValue: {
    color: '#f8fbff',
    fontSize: 26,
    fontWeight: '800',
    marginTop: 4,
  },
  sectionSubtitle: {
    color: '#5c7593',
    fontSize: 13,
    lineHeight: 18,
  },
  sectionTitle: {
    color: '#102947',
    fontSize: 16,
    fontWeight: '800',
  },
  streamDot: {
    borderRadius: 999,
    height: 8,
    width: 8,
  },
  streamPill: {
    alignItems: 'center',
    backgroundColor: 'rgba(8, 17, 32, 0.5)',
    borderRadius: 999,
    columnGap: 6,
    flexDirection: 'row',
    paddingHorizontal: 10,
    paddingVertical: 6,
  },
  streamText: {
    color: '#d2deee',
    fontSize: 12,
    fontWeight: '700',
    letterSpacing: 0.5,
  },
  subBrand: {
    color: '#d2deee',
    fontSize: 13,
    marginTop: 2,
  },
  trickRow: {
    columnGap: 10,
    flexDirection: 'row',
    flexWrap: 'wrap',
    rowGap: 10,
  },
  wrapper: {
    alignSelf: 'center',
    maxWidth: 720,
    rowGap: 16,
    width: '100%',
  },
  yourTurn: {
    color: '#b54434',
    fontSize: 12,
    fontWeight: '800',
    letterSpacing: 0.6,
    textTransform: 'uppercase',
  },
});
